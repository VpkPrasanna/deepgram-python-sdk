# Copyright 2023-2024 Deepgram SDK contributors. All Rights Reserved.
# Use of this source code is governed by a MIT license that can be found in the LICENSE file.
# SPDX-License-Identifier: MIT
import asyncio
import json
import logging
from typing import Dict, Union, Optional, cast, Any

import websockets
from websockets.client import WebSocketClientProtocol

from deepgram.utils import verboselogs
from ....options import DeepgramClientOptions
from ..enums import LiveTranscriptionEvents
from ..helpers import convert_to_websocket_url, append_query_params
from ..errors import DeepgramError

from .response import (
    OpenResponse,
    LiveResultResponse,
    MetadataResponse,
    SpeechStartedResponse,
    UtteranceEndResponse,
    CloseResponse,
    ErrorResponse,
    UnhandledResponse,
)
from .options import LiveOptions

ONE_SECOND = 1
DEEPGRAM_INTERVAL = 5
PING_INTERVAL = 20


class AsyncLiveClient:  # pylint: disable=too-many-instance-attributes
    """
    Client for interacting with Deepgram's live transcription services over WebSockets.

     This class provides methods to establish a WebSocket connection for live transcription and handle real-time transcription events.

     Args:
         config (DeepgramClientOptions): all the options for the client.
    """

    _logger: verboselogs.VerboseLogger
    _config: DeepgramClientOptions
    _endpoint: str
    _websocket_url: str

    _socket: WebSocketClientProtocol
    _event_handlers: Dict[LiveTranscriptionEvents, list]
    _listen_thread: asyncio.Task
    _keep_alive_thread: asyncio.Task

    _kwargs: Optional[Dict] = None
    _addons: Optional[Dict] = None
    _options: Optional[Dict] = None
    _headers: Optional[Dict] = None

    def __init__(self, config: DeepgramClientOptions):
        if config is None:
            raise DeepgramError("Config are required")

        self._logger = verboselogs.VerboseLogger(__name__)
        self._logger.addHandler(logging.StreamHandler())
        self._logger.setLevel(config.verbose)

        self._config = config
        self._endpoint = "v1/listen"
        self._exit_event = asyncio.Event()
        self._event_handlers = {
            event: [] for event in LiveTranscriptionEvents.__members__.values()
        }
        self._websocket_url = convert_to_websocket_url(self._config.url, self._endpoint)

    # pylint: disable=too-many-branches,too-many-statements
    async def start(
        self,
        options: Optional[Union[LiveOptions, Dict]] = None,
        addons: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        members: Optional[Dict] = None,
        **kwargs,
    ) -> bool:
        """
        Starts the WebSocket connection for live transcription.
        """
        self._logger.debug("AsyncLiveClient.start ENTER")
        self._logger.info("options: %s", options)
        self._logger.info("addons: %s", addons)
        self._logger.info("headers: %s", headers)
        self._logger.info("members: %s", members)
        self._logger.info("kwargs: %s", kwargs)

        if isinstance(options, LiveOptions) and not options.check():
            self._logger.error("options.check failed")
            self._logger.debug("AsyncLiveClient.start LEAVE")
            raise DeepgramError("Fatal transcription options error")

        self._addons = addons
        self._headers = headers

        # add "members" as members of the class
        if members is not None:
            self.__dict__.update(members)

        # set kwargs as members of the class
        if kwargs is not None:
            self._kwargs = kwargs
        else:
            self._kwargs = {}

        if isinstance(options, LiveOptions):
            self._logger.info("LiveOptions switching class -> dict")
            self._options = cast(Dict[str, str], options.to_dict())
        elif options is not None:
            self._options = options
        else:
            self._options = {}

        combined_options = self._options
        if self._addons is not None:
            self._logger.info("merging addons to options")
            combined_options.update(self._addons)
            self._logger.info("new options: %s", combined_options)
        self._logger.debug("combined_options: %s", combined_options)

        combined_headers = self._config.headers
        if self._headers is not None:
            self._logger.info("merging headers to options")
            combined_headers.update(self._headers)
            self._logger.info("new headers: %s", combined_headers)
        self._logger.debug("combined_headers: %s", combined_headers)

        url_with_params = append_query_params(self._websocket_url, combined_options)

        try:
            self._socket = await websockets.connect(
                url_with_params,
                extra_headers=combined_headers,
                ping_interval=PING_INTERVAL,
            )
            self._exit_event.clear()

            # listen thread
            self._listen_thread = asyncio.create_task(self._listening())

            # keepalive thread
            if self._config.options.get("keepalive") == "true":
                self._logger.notice("keepalive is enabled")
                self._keep_alive_thread = asyncio.create_task(self._keep_alive())
            else:
                self._logger.notice("keepalive is disabled")

            # push open event
            await self._emit(
                LiveTranscriptionEvents(LiveTranscriptionEvents.Open),
                OpenResponse(type=LiveTranscriptionEvents.Open),
            )

            self._logger.notice("start succeeded")
            self._logger.debug("AsyncLiveClient.start LEAVE")
            return True
        except websockets.ConnectionClosed as e:
            self._logger.error("ConnectionClosed in AsyncLiveClient.start: %s", e)
            self._logger.debug("AsyncLiveClient.start LEAVE")
            if self._config.options.get("termination_exception_connect") == "true":
                raise
            return False
        except websockets.exceptions.WebSocketException as e:
            self._logger.error("WebSocketException in AsyncLiveClient.start: %s", e)
            self._logger.debug("AsyncLiveClient.start LEAVE")
            if self._config.options.get("termination_exception_connect") == "true":
                raise
            return False
        except Exception as e:  # pylint: disable=broad-except
            self._logger.error("WebSocketException in AsyncLiveClient.start: %s", e)
            self._logger.debug("AsyncLiveClient.start LEAVE")
            if self._config.options.get("termination_exception_connect") == "true":
                raise
            return False

    # pylint: enable=too-many-branches,too-many-statements

    def on(self, event: LiveTranscriptionEvents, handler) -> None:
        """
        Registers event handlers for specific events.
        """
        self._logger.info("event fired: %s", event)
        if event in LiveTranscriptionEvents.__members__.values() and callable(handler):
            self._event_handlers[event].append(handler)

    # triggers the registered event handlers for a specific event
    async def _emit(self, event: LiveTranscriptionEvents, *args, **kwargs) -> None:
        """
        Emits events to the registered event handlers.
        """
        for handler in self._event_handlers[event]:
            if asyncio.iscoroutinefunction(handler):
                await handler(self, *args, **kwargs)
            else:
                asyncio.create_task(handler(self, *args, **kwargs))

    # pylint: disable=too-many-return-statements,too-many-statements,too-many-locals
    async def _listening(self) -> None:
        """
        Listens for messages from the WebSocket connection.
        """
        self._logger.debug("AsyncLiveClient._listening ENTER")

        while True:
            try:
                if self._exit_event.is_set():
                    self._logger.notice("_listening exiting gracefully")
                    self._logger.debug("AsyncLiveClient._listening LEAVE")
                    return

                if self._socket is None:
                    self._logger.warning("socket is empty")
                    self._logger.debug("AsyncLiveClient._listening LEAVE")
                    return

                message = str(await self._socket.recv())

                if message is None:
                    self._logger.spam("message is None")
                    continue

                data = json.loads(message)
                response_type = data.get("type")
                self._logger.debug("response_type: %s, data: %s", response_type, data)

                match response_type:
                    case LiveTranscriptionEvents.Open:
                        open_result: OpenResponse = OpenResponse.from_json(message)
                        self._logger.verbose("OpenResponse: %s", open_result)
                        await self._emit(
                            LiveTranscriptionEvents(LiveTranscriptionEvents.Open),
                            open=open_result,
                            **dict(cast(Dict[Any, Any], self._kwargs)),
                        )
                    case LiveTranscriptionEvents.Transcript:
                        msg_result: LiveResultResponse = LiveResultResponse.from_json(
                            message
                        )
                        self._logger.verbose("LiveResultResponse: %s", msg_result)
                        await self._emit(
                            LiveTranscriptionEvents(LiveTranscriptionEvents.Transcript),
                            result=msg_result,
                            **dict(cast(Dict[Any, Any], self._kwargs)),
                        )
                    case LiveTranscriptionEvents.Metadata:
                        meta_result: MetadataResponse = MetadataResponse.from_json(
                            message
                        )
                        self._logger.verbose("MetadataResponse: %s", meta_result)
                        await self._emit(
                            LiveTranscriptionEvents(LiveTranscriptionEvents.Metadata),
                            metadata=meta_result,
                            **dict(cast(Dict[Any, Any], self._kwargs)),
                        )
                    case LiveTranscriptionEvents.SpeechStarted:
                        ss_result: SpeechStartedResponse = (
                            SpeechStartedResponse.from_json(message)
                        )
                        self._logger.verbose("SpeechStartedResponse: %s", ss_result)
                        await self._emit(
                            LiveTranscriptionEvents(
                                LiveTranscriptionEvents.SpeechStarted
                            ),
                            speech_started=ss_result,
                            **dict(cast(Dict[Any, Any], self._kwargs)),
                        )
                    case LiveTranscriptionEvents.UtteranceEnd:
                        ue_result: UtteranceEndResponse = (
                            UtteranceEndResponse.from_json(message)
                        )
                        self._logger.verbose("UtteranceEndResponse: %s", ue_result)
                        await self._emit(
                            LiveTranscriptionEvents(
                                LiveTranscriptionEvents.UtteranceEnd
                            ),
                            utterance_end=ue_result,
                            **dict(cast(Dict[Any, Any], self._kwargs)),
                        )
                    case LiveTranscriptionEvents.Close:
                        close_result: CloseResponse = CloseResponse.from_json(message)
                        self._logger.verbose("CloseResponse: %s", close_result)
                        await self._emit(
                            LiveTranscriptionEvents(LiveTranscriptionEvents.Close),
                            close=close_result,
                            **dict(cast(Dict[Any, Any], self._kwargs)),
                        )
                    case LiveTranscriptionEvents.Error:
                        err_error: ErrorResponse = ErrorResponse.from_json(message)
                        self._logger.verbose("ErrorResponse: %s", err_error)
                        await self._emit(
                            LiveTranscriptionEvents(LiveTranscriptionEvents.Error),
                            error=err_error,
                            **dict(cast(Dict[Any, Any], self._kwargs)),
                        )
                    case _:
                        self._logger.warning(
                            "Unknown Message: response_type: %s, data: %s",
                            response_type,
                            data,
                        )
                        unhandled_error: UnhandledResponse = UnhandledResponse(
                            type=LiveTranscriptionEvents(
                                LiveTranscriptionEvents.Unhandled
                            ),
                            raw=message,
                        )
                        await self._emit(
                            LiveTranscriptionEvents(LiveTranscriptionEvents.Unhandled),
                            unhandled=unhandled_error,
                            **dict(cast(Dict[Any, Any], self._kwargs)),
                        )

            except websockets.exceptions.ConnectionClosedOK as e:
                self._logger.notice(f"_listening({e.code}) exiting gracefully")
                self._logger.debug("AsyncLiveClient._listening LEAVE")
                return

            except websockets.exceptions.ConnectionClosed as e:
                if e.code == 1000:
                    self._logger.notice(f"_listening({e.code}) exiting gracefully")
                    self._logger.debug("AsyncLiveClient._listening LEAVE")
                    return

                self._logger.error(
                    "ConnectionClosed in AsyncLiveClient._listening with code %s: %s",
                    e.code,
                    e.reason,
                )
                cc_error: ErrorResponse = ErrorResponse(
                    "ConnectionClosed in AsyncLiveClient._listening",
                    f"{e}",
                    "ConnectionClosed",
                )
                await self._emit(
                    LiveTranscriptionEvents(LiveTranscriptionEvents.Error),
                    error=cc_error,
                    **dict(cast(Dict[Any, Any], self._kwargs)),
                )

                # signal exit and close
                await self._signal_exit()

                self._logger.debug("AsyncLiveClient._listening LEAVE")

                if self._config.options.get("termination_exception") == "true":
                    raise
                return

            except websockets.exceptions.WebSocketException as e:
                self._logger.error(
                    "WebSocketException in AsyncLiveClient._listening: %s", e
                )
                ws_error: ErrorResponse = ErrorResponse(
                    "WebSocketException in AsyncLiveClient._listening",
                    f"{e}",
                    "WebSocketException",
                )
                await self._emit(
                    LiveTranscriptionEvents(LiveTranscriptionEvents.Error),
                    error=ws_error,
                    **dict(cast(Dict[Any, Any], self._kwargs)),
                )

                # signal exit and close
                await self._signal_exit()

                self._logger.debug("AsyncLiveClient._listening LEAVE")

                if self._config.options.get("termination_exception") == "true":
                    raise
                return

            except Exception as e:  # pylint: disable=broad-except
                self._logger.error("Exception in AsyncLiveClient._listening: %s", e)
                e_error: ErrorResponse = ErrorResponse(
                    "Exception in AsyncLiveClient._listening",
                    f"{e}",
                    "Exception",
                )
                await self._emit(
                    LiveTranscriptionEvents(LiveTranscriptionEvents.Error),
                    error=e_error,
                    **dict(cast(Dict[Any, Any], self._kwargs)),
                )

                # signal exit and close
                await self._signal_exit()

                self._logger.debug("AsyncLiveClient._listening LEAVE")

                if self._config.options.get("termination_exception") == "true":
                    raise
                return

    # pylint: enable=too-many-return-statements,too-many-statements

    # pylint: disable=too-many-return-statements
    async def _keep_alive(self) -> None:
        """
        Sends keepalive messages to the WebSocket connection.
        """
        self._logger.debug("AsyncLiveClient._keep_alive ENTER")

        counter = 0
        while True:
            try:
                counter += 1
                await asyncio.sleep(ONE_SECOND)

                if self._exit_event.is_set():
                    self._logger.notice("_keep_alive exiting gracefully")
                    self._logger.debug("AsyncLiveClient._keep_alive LEAVE")
                    return

                if self._socket is None:
                    self._logger.notice("socket is None, exiting keep_alive")
                    self._logger.debug("AsyncLiveClient._keep_alive LEAVE")
                    return

                # deepgram keepalive
                if counter % DEEPGRAM_INTERVAL == 0:
                    self._logger.verbose("Sending KeepAlive...")
                    await self.send(json.dumps({"type": "KeepAlive"}))

            except websockets.exceptions.ConnectionClosedOK as e:
                self._logger.notice(f"_keep_alive({e.code}) exiting gracefully")
                self._logger.debug("AsyncLiveClient._keep_alive LEAVE")
                return

            except websockets.exceptions.ConnectionClosed as e:
                if e.code == 1000:
                    self._logger.notice(f"_keep_alive({e.code}) exiting gracefully")
                    self._logger.debug("AsyncLiveClient._keep_alive LEAVE")
                    return

                self._logger.error(
                    "ConnectionClosed in AsyncLiveClient._keep_alive with code %s: %s",
                    e.code,
                    e.reason,
                )
                cc_error: ErrorResponse = ErrorResponse(
                    "ConnectionClosed in AsyncLiveClient._keep_alive",
                    f"{e}",
                    "ConnectionClosed",
                )
                await self._emit(
                    LiveTranscriptionEvents(LiveTranscriptionEvents.Error),
                    error=cc_error,
                    **dict(cast(Dict[Any, Any], self._kwargs)),
                )

                # signal exit and close
                await self._signal_exit()

                self._logger.debug("AsyncLiveClient._keep_alive LEAVE")

                if self._config.options.get("termination_exception") == "true":
                    raise
                return

            except websockets.exceptions.WebSocketException as e:
                self._logger.error(
                    "WebSocketException in AsyncLiveClient._keep_alive: %s", e
                )
                ws_error: ErrorResponse = ErrorResponse(
                    "WebSocketException in AsyncLiveClient._keep_alive",
                    f"{e}",
                    "Exception",
                )
                await self._emit(
                    LiveTranscriptionEvents(LiveTranscriptionEvents.Error),
                    error=ws_error,
                    **dict(cast(Dict[Any, Any], self._kwargs)),
                )

                # signal exit and close
                await self._signal_exit()

                self._logger.debug("AsyncLiveClient._keep_alive LEAVE")

                if self._config.options.get("termination_exception") == "true":
                    raise
                return

            except Exception as e:  # pylint: disable=broad-except
                self._logger.error("Exception in AsyncLiveClient._keep_alive: %s", e)
                e_error: ErrorResponse = ErrorResponse(
                    "Exception in AsyncLiveClient._keep_alive",
                    f"{e}",
                    "Exception",
                )
                self._logger.error(
                    "Exception in AsyncLiveClient._keep_alive: %s", str(e)
                )
                await self._emit(
                    LiveTranscriptionEvents(LiveTranscriptionEvents.Error),
                    error=e_error,
                    **dict(cast(Dict[Any, Any], self._kwargs)),
                )

                # signal exit and close
                await self._signal_exit()

                self._logger.debug("AsyncLiveClient._keep_alive LEAVE")

                if self._config.options.get("termination_exception") == "true":
                    raise
                return

    async def send(self, data: Union[str, bytes]) -> bool:
        """
        Sends data over the WebSocket connection.
        """
        self._logger.spam("AsyncLiveClient.send ENTER")

        if self._exit_event.is_set():
            self._logger.notice("send exiting gracefully")
            self._logger.debug("AsyncLiveClient.send LEAVE")
            return False

        if self._socket is not None:
            try:
                await self._socket.send(data)
            except websockets.exceptions.ConnectionClosedOK as e:
                self._logger.notice(f"send() exiting gracefully: {e.code}")
                self._logger.debug("AsyncLiveClient.send LEAVE")
                if self._config.options.get("termination_exception_send") == "true":
                    raise
                return True
            except websockets.exceptions.ConnectionClosed as e:
                if e.code == 1000:
                    self._logger.notice(f"send({e.code}) exiting gracefully")
                    self._logger.debug("AsyncLiveClient.send LEAVE")
                    if self._config.options.get("termination_exception_send") == "true":
                        raise
                    return True

                self._logger.error("send() failed - ConnectionClosed: %s", str(e))
                self._logger.spam("AsyncLiveClient.send LEAVE")
                if self._config.options.get("termination_exception_send") == "true":
                    raise
                return False
            except websockets.exceptions.WebSocketException as e:
                self._logger.error("send() failed - WebSocketException: %s", str(e))
                self._logger.spam("AsyncLiveClient.send LEAVE")
                if self._config.options.get("termination_exception_send") == "true":
                    raise
                return False
            except Exception as e:  # pylint: disable=broad-except
                self._logger.error("send() failed - Exception: %s", str(e))
                self._logger.spam("AsyncLiveClient.send LEAVE")
                if self._config.options.get("termination_exception_send") == "true":
                    raise
                return False

            self._logger.spam("send() succeeded")
            self._logger.spam("AsyncLiveClient.send LEAVE")
            return True

        self._logger.spam("send() failed. socket is None")
        self._logger.spam("AsyncLiveClient.send LEAVE")
        return False

    # pylint: enable=too-many-return-statements

    async def finalize(self) -> bool:
        """
        Finalizes the Transcript connection by flushing it
        """
        self._logger.spam("AsyncLiveClient.finalize ENTER")

        if self._exit_event.is_set():
            self._logger.notice("finalize exiting gracefully")
            self._logger.debug("AsyncLiveClient.finalize LEAVE")
            return False

        if self._socket is not None:
            self._logger.notice("sending Finalize...")
            ret = await self.send(json.dumps({"type": "Finalize"}))

            if not ret:
                self._logger.error("finalize failed")
                self._logger.spam("AsyncLiveClient.finalize LEAVE")
                return False

        self._logger.notice("finalize succeeded")
        self._logger.spam("AsyncLiveClient.finalize LEAVE")

        return True

    async def finish(self) -> bool:
        """
        Closes the WebSocket connection gracefully.
        """
        self._logger.debug("AsyncLiveClient.finish ENTER")

        # signal exit
        await self._signal_exit()

        # stop the threads
        self._logger.verbose("cancelling tasks...")
        try:
            # Before cancelling, check if the tasks were created
            tasks = []
            if self._config.options.get("keepalive") == "true":
                if self._keep_alive_thread is not None:
                    self._keep_alive_thread.cancel()
                    tasks.append(self._keep_alive_thread)
            if self._listen_thread is not None:
                self._listen_thread.cancel()
                tasks.append(self._listen_thread)

            # Use asyncio.gather to wait for tasks to be cancelled
            await asyncio.gather(*filter(None, tasks), return_exceptions=True)
            self._logger.notice("threads joined")

            self._logger.notice("finish succeeded")
            self._logger.spam("AsyncLiveClient.finish LEAVE")
            return True

        except asyncio.CancelledError as e:
            self._logger.error("tasks cancelled error: %s", e)
            self._logger.debug("AsyncLiveClient.finish LEAVE")
            return False

    async def _signal_exit(self) -> None:
        # send close event
        self._logger.verbose("closing socket...")
        if self._socket is not None:
            self._logger.verbose("send CloseStream...")
            try:
                # if the socket connection is closed, the following line might throw an error
                await self.send(json.dumps({"type": "CloseStream"}))
            except websockets.exceptions.ConnectionClosedOK as e:
                self._logger.notice("_signal_exit  - ConnectionClosedOK: %s", e.code)
            except websockets.exceptions.ConnectionClosed as e:
                self._logger.notice("_signal_exit  - ConnectionClosed: %s", e.code)
            except websockets.exceptions.WebSocketException as e:
                self._logger.error("_signal_exit - WebSocketException: %s", str(e))
            except Exception as e:  # pylint: disable=broad-except
                self._logger.error("_signal_exit - Exception: %s", str(e))

            # push close event
            try:
                await self._emit(
                    LiveTranscriptionEvents(LiveTranscriptionEvents.Close),
                    close=CloseResponse(type=LiveTranscriptionEvents.Close),
                    **dict(cast(Dict[Any, Any], self._kwargs)),
                )
            except Exception as e:  # pylint: disable=broad-except
                self._logger.error("_emit - Exception: %s", e)

            # wait for task to send
            await asyncio.sleep(0.5)

        # signal exit
        self._exit_event.set()

        # closes the WebSocket connection gracefully
        self._logger.verbose("clean up socket...")
        if self._socket is not None:
            self._logger.verbose("socket.wait_closed...")
            try:
                await self._socket.close()
            except websockets.exceptions.WebSocketException as e:
                self._logger.error("socket.wait_closed failed: %s", e)

        self._socket = None  # type: ignore
