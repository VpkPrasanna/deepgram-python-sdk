# Deepgram Python SDK

 [![Discord](https://dcbadge.vercel.app/api/server/xWRaCDBtW4?style=flat)](https://discord.gg/xWRaCDBtW4) [![GitHub Workflow Status](https://img.shields.io/github/workflow/status/deepgram/deepgram-python-sdk/CI)](https://github.com/deepgram/deepgram-python-sdk/actions/workflows/CI.yml) [![PyPI](https://img.shields.io/pypi/v/deepgram-sdk)](https://pypi.org/project/deepgram-sdk/)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-v2.0%20adopted-ff69b4.svg?style=flat-rounded)](./.github/CODE_OF_CONDUCT.md)

Official Python SDK for [Deepgram](https://www.deepgram.com/). Power your apps with world-class speech and Language AI models.

> This SDK only supports hosted usage of api.deepgram.com.

* [Deepgram Python SDK](#deepgram-python-sdk)
* [Documentation](#documentation)
* [Getting an API Key](#getting-an-api-key)
* [Installation](#installation)
* [Examples](#examples)
* [Testing](#testing)
* [Configuration](#configuration)
  * [Custom API Endpoint] [#custom-api-endpoint]
* [Transcription](#transcription)
  * [Remote Files](#remote-files)
  * [Local Files](#local-files)
  * [Live Audio](#live-audio)
  * [Parameters](#parameters)
* [Projects](#projects)
  * [Get Projects](#get-projects)
  * [Get Project](#get-project)
  * [Update Project](#update-project)
* [Keys](#keys)
  * [List Keys](#list-keys)
  * [Get Key](#get-key)
  * [Create Key](#create-key)
  * [Delete Key](#delete-key)
* [Members](#members)
  * [Get Members](#get-members)
  * [Remove Member](#remove-member)
* [Scopes](#scopes)
  * [Get Member Scopes](#get-member-scopes)
  * [Update Scope](#update-scope)
* [Invitations](#invitations)
  * [List Invites](#list-invites)
  * [Send Invite](#send-invite)
  * [Delete Invite](#delete-invite)
  * [Leave Project](#leave-project)
* [Usage](#usage)
  * [Get All Requests](#get-all-requests)
  * [Get Request](#get-request)
  * [Get Fields](#get-fields)
* [Billing](#billing)
  * [Get All Balances](#get-all-balances)
  * [Get Balance](#get-balance)
* [Development and Contributing](#development-and-contributing)
* [Getting Help](#getting-help)

# Documentation

You can learn more about the Deepgram API at [developers.deepgram.com](https://developers.deepgram.com/docs).

# Getting an API Key

🔑 To access the Deepgram API you will need a [free Deepgram API Key](https://console.deepgram.com/signup?jump=keys).

# Installation

```sh
pip install deepgram-sdk
```

# Examples

To quickly get started with examples for prerecorded and streaming, run the files in the example folder. See the README in that folder for more information on getting started.

# Testing

## Setup

Run the following command to install `pytest` and `pytest-cov` as dev dependencies.

```sh
pip install -r requirements.txt
```

## Run All Tests

## Setup

```sh
pip install pytest
pip install pytest-cov
```

## Run All Tests

```sh
pytest --api-key <key> tests/
```

## Test Coverage Report

```sh
pytest --cov=deepgram --api-key <key> tests/
```

# Configuration

To setup the configuration of the Deepgram Client, do the following:

* Import the Deepgram client
* Create a Deepgram Client instance and pass in credentials to the constructor.

```python
from deepgram import Deepgram

DEEPGRAM_API_KEY = 'YOUR_API_KEY'
deepgram = Deepgram(DEEPGRAM_API_KEY)
```

## Custom API Endpoint

In order to point the SDK at a different API environment (e.g., for on-prem deployments), you can pass in an object setting the `api_url` when initializing the Deepgram client.

```python
dg_client = Deepgram({ 
  "api_key": DEEPGRAM_API_KEY, 
  "api_url": "http://localhost:8080/v1/listen" 
})
```

# Transcription

## Remote Files

```python
from deepgram import Deepgram
import asyncio, json

DEEPGRAM_API_KEY = 'YOUR_API_KEY'
FILE_URL = 'https://static.deepgram.com/examples/interview_speech-analytics.wav'

async def main():
  # Initializes the Deepgram SDK
  deepgram = Deepgram(DEEPGRAM_API_KEY)
  source = {'url': FILE_URL}
  response = await asyncio.create_task(
      deepgram.transcription.prerecorded(source, {
          'smart_format': True,
          'model': 'nova',
      }))
  print(json.dumps(response, indent=4))

asyncio.run(main())
```

## Local Files

```python
from deepgram import Deepgram
import json

DEEPGRAM_API_KEY = 'YOUR_API_KEY'
PATH_TO_FILE = 'some/file.wav'

def main():
    # Initializes the Deepgram SDK
    deepgram = Deepgram(DEEPGRAM_API_KEY)
    # Open the audio file
    with open(PATH_TO_FILE, 'rb') as audio:
        # ...or replace mimetype as appropriate
        source = {'buffer': audio, 'mimetype': 'audio/wav'}
        response = deepgram.transcription.sync_prerecorded(source, {'punctuate': True})
        print(json.dumps(response, indent=4))

main()
```

## Live Audio

```python
from deepgram import Deepgram
import asyncio
import aiohttp

# Your Deepgram API Key
DEEPGRAM_API_KEY = 'YOUR_API_KEY'

# URL for the audio you would like to stream
URL = 'http://stream.live.vc.bbcmedia.co.uk/bbc_world_service'

async def main():
  # Initialize the Deepgram SDK
  deepgram = Deepgram(DEEPGRAM_API_KEY)

  # Create a websocket connection to Deepgram
  # In this example, punctuation is turned on, interim results are turned off, and language is set to US English.
  try:
    deepgramLive = await deepgram.transcription.live({ 'punctuate': True, 'interim_results': False, 'language': 'en-US' })
  except Exception as e:
    print(f'Could not open socket: {e}')
    return

# Listen for the connection to close
  deepgramLive.registerHandler(deepgramLive.event.CLOSE, lambda c: print(f'Connection closed with code {c}.'))

  # Listen for any transcripts received from Deepgram and write them to the console
  deepgramLive.registerHandler(deepgramLive.event.TRANSCRIPT_RECEIVED, print)

  # Listen for the connection to open and send streaming audio from the URL to Deepgram
  async with aiohttp.ClientSession() as session:
    async with session.get(URL) as audio:
      while True:
        data = await audio.content.readany()
        deepgramLive.send(data)

        # If there's no data coming from the livestream then break out of the loop
        if not data:
            break

  # Indicate that we've finished sending data by sending the customary zero-byte message to the Deepgram streaming endpoint, and wait until we get back the final summary metadata object
  await deepgramLive.finish()

asyncio.run(main())
```

## Parameters

Query parameters like `punctuate` are added as part of the `TranscriptionOptions` `dict` in the `.prerecorded`/`.live` transcription call.
Multiple query parameters can be added similarly, and any dict will do - the types are provided for reference/convenience.

```python
response = await dg_client.transcription.prerecorded(source, {'punctuate': True, 'keywords': ['first:5', 'second']})
```

Depending on your preference, you can also add parameters as named arguments, instead.

```python
response = await dg_client.transcription.prerecorded(source, punctuate=True, keywords=['first:5', 'second'])
```

# Projects

The `Deepgram.projects` object provides access to manage projects associated with the API key you provided when instantiating the Deepgram client.

## Get Projects

### Get Projects Example Request

```python
projects = await deepgram.projects.list()
```

### Get Projects Response

```ts
{
  projects: [
    {
      project_id: String,
      name: String,
    },
  ],
}
```

## Get Project

Retrieves a project based on the provided project id.

### Get a Project Parameters

| Parameter  | Type   | Description                                     |
| ---------- | ------ | ----------------------------------------------- |
| project_id | String | A unique identifier for the project to retrieve |

### Get a Project Example Request

```python
project = await deepgram.projects.get(PROJECT_ID)
```

### Get a Project Response

```ts
{
  project_id: String,
  name: String,
}
```

## Update Project

Updates a project based on a provided project object.

### Update Project Parameters

| Parameter | Type   | Description                                                                     |
| --------- | ------ | ------------------------------------------------------------------------------- |
| project   | Object | Object representing a project. Must contain `project_id` and `name` properties. |

### Update a Project Example Request

```python
updateResponse = await deepgram.projects.update(project)
```

### Update a Project Response

```ts
{
 message: String;
}
```

# Keys

The `Deepgram.keys` object provides access to manage keys associated with your projects. Every function provided will required a `PROJECT_ID` that your current has access to manage.

## List Keys

You can retrieve all keys for a given project using the `keys.list` function.

### List Project API Keys Parameters

| Parameter  | Type   | Description                                                         |
| ---------- | ------ | ------------------------------------------------------------------- |
| project_id | String | A unique identifier for the project the API key will be created for |

### List Project Keys Example Request

```python
response = await deepgram.keys.list(PROJECT_ID)
```

### List Keys Response

```ts
{
 api_keys: [
  {
   api_key_id: string,
   comment: string,
   created: string,
   scopes: Array<string>,
  },
 ];
}
```

## Create Key

Create a new API key for a project using the `keys.create` function with a name for the key.

### Create API Key Parameters

| Parameter       | Type   | Description                                                         |
| --------------- | ------ | ------------------------------------------------------------------- |
| project_id      | String | A unique identifier for the project the API key will be created for |
| comment_for_key | String | A comment to denote what the API key is for                         |
| scopes          | Array  | A permissions scopes of the key to create                           |

### Create API Key Example Request

```python
response = await deepgram.keys.create(PROJECT_ID, COMMENT_FOR_KEY, SCOPES)
```

### Create API Key Response

```ts
{
  api_key_id: string,
  key: string,
  comment: string,
  created: string,
  scopes: string[]
}
```

## Delete Key

Delete an existing API key using the `keys.delete` method with project id and key id to delete.

### Delete Key Parameters

| Parameter  | Type   | Description                                                         |
| ---------- | ------ | ------------------------------------------------------------------- |
| project_id | String | A unique identifier for the project the API key will be delete from |
| key_id     | String | A unique identifier for the API key to delete                       |

### Delete Key Example Request

```python
await deepgram.keys.delete(PROJECT_ID, KEY_ID)
```

### Delete Key Response

The `keys.delete` function returns a void.

# Members

The `deepgram.members` object provides access to the members endpoints of the Deepgram API. Each request is project based and will require a `project_id`.

## Get Members

You can retrieve all members on a given project using the `members.list_members` function.

### Get Members Parameters

| Parameter  | Type   | Description                                                        |
| ---------- | ------ | ------------------------------------------------------------------ |
| project_id | String | A unique identifier for the project you wish to see the members of |

### Get Members Example Request

```python
response = await deepgram.members.list_members(PROJECT_ID)
```

### Get Members Response

```ts
{
  members: [
    {
      member_id: string,
      scopes: Array<string>
      email: string,
      first_name: string,
      last_name: string,
    },
  ];
}
```

## Remove Member

You can remove a member from a given project using the `members.remove_member` function.

### Remove Member Parameters

| Parameter  | Type   | Description                                                        |
| ---------- | ------ | ------------------------------------------------------------------ |
| project_id | String | A unique identifier for the project you wish to see the members of |
| member_id  | String | A unique identifier for the member you wish to remove              |

### Remove Member Example Request

```python
response = await deepgram.members.remove_member(PROJECT_ID, MEMBER_ID)
```

### Remove Member Response

```ts
{
 message: string;
}
```

# Scopes

The `deepgram.scopes` object provides access to the scopes endpoints of the Deepgram API. Each request is project based and will require a `project_id`.

## Get Member Scopes

You can retrieve all scopes of a member on a given project using the `scopes.get_scope` function.

### Get Member Scopes Parameters

| Parameter  | Type   | Description                                                              |
| ---------- | ------ | ------------------------------------------------------------------------ |
| project_id | String | A unique identifier for the project you wish to see the member scopes of |
| member_id  | String | A unique identifier for the member you wish to see member scopes of      |

### Get Member Scopes Example Request

```python
response = await deepgram.scopes.get_scope(PROJECT_ID, MEMBER_ID)
```

### Get Member Scopes Response

```ts
{
  scopes: string[]
}
```

## Update Scope

You can update the scope of a member on a given project using the `scopes.update_scope` function.

### Update Scope Parameters

| Parameter  | Type   | Description                                                                 |
| ---------- | ------ | --------------------------------------------------------------------------- |
| project_id | String | A unique identifier for the project you wish to update the member scopes of |
| member_id  | String | A unique identifier for the member you wish to update member scopes of      |
| scopes     | String | The scope you wish to update the member to                                  |

### Update Scope Example Request

```python
response = await deepgram.scopes.update_scope(PROJECT_ID, MEMBER_ID, 'member')
```

### Update Scope Response

```ts
{
 message: string;
}
```

# Invitations

The `deepgram.invitations` object provides access to the invites endpoints of the Deepgram API. Each request is project based and will require a `project_id`.

## List Invites

You can retrieve all active invitations on a given project using the `invitations.list_invitations` function.

### List Invites Parameters

| Parameter  | Type   | Description                                                            |
| ---------- | ------ | ---------------------------------------------------------------------- |
| project_id | String | A unique identifier for the project you wish to see the invitations of |

### List Invites Example Request

```python
response = await deepgram.invitations.list_invitations(PROJECT_ID)
```

### List Invites Response

```ts
{
 members: [
  {
   email: string,
   scope: string,
  },
 ];
}
```

## Send Invite

You can send an invitation to a given email address to join a given project using the `invitations.send_invitation` function.

### Send Invite Parameters

| Parameter  | Type   | Description                                                                                                                            |
| ---------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| project_id | String | A unique identifier for the project you wish to send an invitation from                                                                |
| option     | Object | An object containing the email address of the person you wish to send an invite to, and the scope you want them to have in the project |

### Send Invite Example Request

```python
response = await deepgram.invitations.send_invitation(PROJECT_ID, {
  email: 'example@email.com',
  scope: 'member',
})
```

### Send Invite Response

```ts
{
 message: string;
}
```

## Delete Invite

Removes the invitation of the specified email from the specified project.

### Delete Invite Parameters

| Parameter  | Type   | Description                                                            |
| ---------- | ------ | ---------------------------------------------------------------------- |
| project_id | String | A unique identifier for the project you wish to remove the invite from |
| email      | String | The email address of the invitee                                       |

### Delete Invite Example Request

```python
response = await deepgram.invitations.remove_invitation(
  PROJECT_ID,
  'example@email.com'
)
```

### Delete Invite Response

```ts
{
 message: string;
}
```

## Leave Project

Removes the authenticated account from the specified project.

### Leave Project Parameters

| Parameter  | Type   | Description                                           |
| ---------- | ------ | ----------------------------------------------------- |
| project_id | String | A unique identifier for the project you wish to leave |

### Leave Project Example Request

```python
response = await deepgram.invitations.leave_project(PROJECT_ID)
```

### Leave Project Response

```ts
{
 message: string;
}
```

# Usage

The `deepgram.usage` object provides access to the usage endpoints of the Deepgram API. Each request is project based and will require a `project_id`.

## Get All Requests

Retrieves transcription requests for a project based on the provided options.

### Get All Requests Parameters

| Parameter  | Type   | Description                                               |
| ---------- | ------ | --------------------------------------------------------- |
| project_id | String | A unique identifier for the project to retrieve usage for |
| options    | Object | Parameters to filter requests. See below.                 |

#### Get All Requests Options

```python
{
  // The time to retrieve requests made since
  // Example: "2020-01-01T00:00:00+00:00"
  start?: String,
  // The time to retrieve requests made until
  // Example: "2021-01-01T00:00:00+00:00"
  end?: String,
  // Page of requests to return
  // Defaults to 0
  page?: Number,
  // Number of requests to return per page
  // Defaults to 10. Maximum of 100
  limit?: Number,
  // Filter by succeeded or failed requests
  // By default, all requests are returned
  status?: 'succeeded' | 'failed'
}
```

### Get All Requests Example Request

```python
response = await deepgram.usage.list_requests(PROJECT_ID, {
  'limit': 10,
  # other options are available
})
```

### Get All Requests Response

```ts
{
  page: Number,
  limit: Number,
  requests?: [
    {
      request_id: String;
      created: String;
      path: String;
      accessor: String;
      response?:  {
        details: {
          usd: Number;
          duration: Number;
          total_audio: Number;
          channels: Number;
          streams: Number;
          model: String;
          method: String;
          tags: String[];
          features: String[];
          config: {
            multichannel?: Boolean;
            interim_results?: Boolean;
            punctuate?: Boolean;
            ner?: Boolean;
            utterances?: Boolean;
            replace?: Boolean;
            profanity_filter?: Boolean;
            keywords?: Boolean;
            diarize?: Boolean;
            search?: Boolean;
            redact?: Boolean;
            alternatives?: Boolean;
            numerals?: Boolean;
          };
        }
      }, ||
      {
        message?: String;
      },
      callback?: {
        code: Number;
        completed: String;
      },
    },
  ];
}
```

## Get Request

Retrieves a specific transcription request for a project based on the provided `projectId` and `requestId`.

### Get Request Parameters

| Parameter  | Type   | Description                                               |
| ---------- | ------ | --------------------------------------------------------- |
| project_id | String | A unique identifier for the project to retrieve usage for |
| request_id | String | Unique identifier of the request to retrieve              |

### Get Request Example Request

```python
response = await deepgram.usage.get_request(PROJECT_ID, REQUEST_ID)
```

### Get Request Response

```ts
{
  request_id: String;
  created: String;
  path: String;
  accessor: String;
  response?:  {
    details: {
      usd: Number;
      duration: Number;
      total_audio: Number;
      channels: Number;
      streams: Number;
      model: String;
      method: String;
      tags: String[];
      features: String[];
      config: {
        multichannel?: Boolean;
        interim_results?: Boolean;
        punctuate?: Boolean;
        ner?: Boolean;
        utterances?: Boolean;
        replace?: Boolean;
        profanity_filter?: Boolean;
        keywords?: Boolean;
        diarize?: Boolean;
        search?: Boolean;
        redact?: Boolean;
        alternatives?: Boolean;
        numerals?: Boolean;
      };
    }
  }, ||
  {
    message?: String;
  },
  callback?: {
    code: Number;
    completed: String;
  }
}
```

## Get Usage

Retrieves aggregated usage data for a project based on the provided options.

### Get Usage Parameters

| Parameter  | Type   | Description                                               |
| ---------- | ------ | --------------------------------------------------------- |
| project_id | String | A unique identifier for the project to retrieve usage for |
| options    | Object | Parameters to filter requests. See below.                 |

#### Get Usage Options

```ts
{
  // The time to retrieve requests made since
  // Example: "2020-01-01T00:00:00+00:00"
  start?: String,
  // The time to retrieve requests made until
  // Example: "2021-01-01T00:00:00+00:00"
  end?: String,
  // Specific identifer for a request
  accessor?: String,
  // Array of tags used in requests
  tag?: String[],
  // Filter requests by method
  method?: "sync" | "async" | "streaming",
  // Filter requests by model used
  model?: String,
  // Filter only requests using multichannel feature
  multichannel?: Boolean,
  // Filter only requests using interim results feature
  interim_results?: Boolean,
  // Filter only requests using the punctuation feature
  punctuate?: Boolean,
  // Filter only requests using ner feature
  ner?: Boolean,
  // Filter only requests using utterances feature
  utterances?: Boolean,
  // Filter only requests using replace feature
  replace?: Boolean,
  // Filter only requests using profanity_filter feature
  profanity_filter?: Boolean,
  // Filter only requests using keywords feature
  keywords?: Boolean,
  // Filter only requests using diarization feature
  diarize?: Boolean,
  // Filter only requests using search feature
  search?: Boolean,
  // Filter only requests using redact feature
  redact?: Boolean,
  // Filter only requests using alternatives feature
  alternatives?: Boolean,
  // Filter only requests using numerals feature
  numerals?: Boolean
}
```

### Get Usage Example Request

```python
response = await deepgram.usage.get_usage(PROJECT_ID, {
  'start': '2020-01-01T00:00:00+00:00',
  # other options are available
})
```

### Get Usage Response

```ts
{
  start: String,
  end: String,
  resolution: {
    units: String,
    amount: Number
  };
  results: [
    {
      start: String,
      end: String,
      hours: Number,
      requests: Number
    }
  ];
}
```

## Get Fields

Retrieves features used by the provided project_id based on the provided options.

### Get Fields Parameters

| Parameter  | Type   | Description                                                     |
| ---------- | ------ | --------------------------------------------------------------- |
| project_id | String | A unique identifier for the project to retrieve fields used for |
| options    | Object | Parameters to filter requests. See below.                       |

#### Get Fields Options

```ts
{
  // The time to retrieve requests made since
  // Example: "2020-01-01T00:00:00+00:00"
  start?: String,
  // The time to retrieve requests made until
  // Example: "2021-01-01T00:00:00+00:00"
  end?: String
}
```

### Get Fields Example Request

```python
response = await deepgram.usage.get_fields(PROJECT_ID, {
  'start': '2020-01-01T00:00:00+00:00',
  # other options are available
})
```

#### Get Fields Response

```ts
{
  tags: String[],
  models: String[],
  processing_methods: String[],
  languages: String[],
  features: String[]
}
```

# Billing

The `deepgram.billing` object provides access to the balances endpoints of the Deepgram API. Each request is project based and will require a `project_id`.

## Get All Balances

You can retrieve all balances on a given project using the `billing.list_balance` function.

### Get All Balances Parameters

| Parameter  | Type   | Description                                                             |
| ---------- | ------ | ----------------------------------------------------------------------- |
| project_id | String | A unique identifier for the project you wish to see the balance info of |

### Get All Balances Example Request

```python
response = await deepgram.billing.list_balance(PROJECT_ID)
```

### Get All Balances Response

```ts
{
  balances: [
      {
      balance_id: string
      amount: number
      units: string
      purchase: string
    }
  ]
}
```

## Get Balance

You can retrieve all balances on a given project using the `billing.get_balance` function.

### Get Balance Parameters

| Parameter  | Type   | Description                                                             |
| ---------- | ------ | ----------------------------------------------------------------------- |
| project_id | String | A unique identifier for the project you wish to see the balance info of |
| balance_id | String | A unique identifier for the balance you wish to see the balance info of |

### Get Balance Example Request

```python
const response = deepgram.billing.get_balance(PROJECT_ID, BALANCE_ID)
```

### Get Balance Response

```ts
{
 balance: {
  balance_id: string;
  amount: number;
  units: string;
  purchase: string;
 }
}
```

# Development and Contributing

Interested in contributing? We ❤️ pull requests!

To make sure our community is safe for all, be sure to review and agree to our
[Code of Conduct](./CODE_OF_CONDUCT.md). Then see the
[Contribution](./CONTRIBUTING.md) guidelines for more information.

# Getting Help

We love to hear from you so if you have questions, comments or find a bug in the
project, let us know! You can either:

* [Open an issue in this repository](https://github.com/deepgram/deepgram-python-sdk/issues/new)
* [Join the Deepgram Github Discussions Community](https://github.com/orgs/deepgram/discussions)
* [Join the Deepgram Discord Community](https://discord.gg/xWRaCDBtW4)
