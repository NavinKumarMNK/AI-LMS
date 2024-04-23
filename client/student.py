from functools import wraps
import asyncio
import json
import logging
import sys
from typing import Dict, List
import traceback
import click
import httpx
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.text import Text
from rich.panel import Panel

from dataclasses import dataclass
import requests
from getpass import getpass
import pathlib
import json
import aiohttp


httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)
logger = logging.getLogger()


def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@dataclass
class JWTClient:

    base_endpoint = "http://0.0.0.0:8000/v1"

    async def create(data):
        endpoint = f"{self.base_endpoint}/chat/create"
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=data) as response:
                if response.status == 201:
                    async for word in response.content:
                        return json.loads(word.decode("utf-8").strip())
                else:
                    raise Exception(f"Request failed with status code: {response.status}")

    async def completion(url, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    if data["stream"]:
                        async for line in response.content.iter_any():
                            yield line.decode("utf-8").strip()
                    else:
                        text = await response.text()
                        yield text
                else:
                    raise Exception(f"Request failed with status code: {response.status}")

    async def patch(url, feedback):
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, params={"feedback": feedback}) as response:
                if response.status == 200:
                    async for word in response.content:
                        print(word.decode("utf-8").strip())
                else:
                    raise Exception(f"Request failed with status code: {response.status}")

    async def generate_text(endpoint_url: str, payload: Dict) -> List[str]:
        result = []
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            if payload["stream"]:
                async with client.stream(
                    method="POST",
                    url=endpoint_url,
                    json=payload,
                    headers=headers,
                    timeout=30,
                    follow_redirects=True,
                ) as response:
                    if response.status_code == 200:
                        async for line in response.aiter_lines():
                            # Parse the line from a JSON string to a dictionary
                            line_dict = json.loads(line)
                            res = line_dict["output"]
                            sys.stdout.write(res)
                            sys.stdout.flush()
                            result.append(res)
                    else:
                        logger.error(f"HTTP status code: {response.status_code}")
                        logger.error(response.text)
                        response.raise_for_status()
            else:
                response = await client.post(
                    endpoint_url, json=payload, headers=headers, timeout=30
                )
                response.raise_for_status()
                result = response.json()

        return result

async def create_chat(client: JWTClient, user_id: str):
    data = {
        "user_id": user_id,
    }
    print(data)
    res = await client.create(data)
    chat_id = res["chat_id"]
    print(chat_id)


@click.command()
@click.option("--host", default="localhost", help="Host")
@click.option("--port", default=5000, help="Port")
@click.option("--stream", default=True, help="Stream")
@click.option("--max-tokens", default=4096, help="Max tokens")
@click.option("--temperature", default=0.3, help="Temperature")
@click.option(
    "--is-prompt",
    default=False,
    help="Format of input, if prompt then \
              set True. Default is False ",
)
@coro
async def main(
    host: str,
    port: int,
    stream: bool,
    max_tokens: int,
    temperature: float,
    is_prompt: bool,
):
    logging.basicConfig(level=logging.INFO)
    console = Console()

    client = JWTClient()
    # client.base_endpoint = f"http://{host}:{port}/v1"


    welcome_message = Text("""Hello, this is MegAcad, your AI Educational Tutor 
You can type the prompts or messages 
Please be polite towards me & Remember, I can make mistakes too """)
    welcome_message = Panel(welcome_message, title="MegAcad AI")
    console.print(welcome_message)
    messages = []
    session = PromptSession(history=FileHistory(".history"))


    user_id = click.prompt("? Enter user id to login", type=str)
    chat_id = await create_chat(client, user_id)


    i = 0
    while i <= 30:
        try:
            user_message = session.prompt(">>> ")
            if user_message == "\\q":
                print("Session Exited")
                break
            elif user_message == "\\n":
                messages = []
                console.clear()
                console.print("New Session")
                console.print(welcome_message)

                chat_id = await create_chat(client, user_id)

                continue
            elif user_message.strip() == "":
                continue
            elif user_message == "\\c":
                console.clear()
                continue
            elif user_message == "\\f":
                feedback = 3
                url = f"http://localhost:8000/v1/chat/{chat_id}/"
                await client.patch(url, feedback)
                print("Feedback received")
                continue


            if is_prompt:
                payload = {
                    "prompt": user_message,
                    "stream": stream,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
            else:
                messages.append({"role": "user", "content": user_message})
                payload = {
                    "messages": messages,
                    "stream": stream,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }

            if stream:
                assistant_message = asyncio.run(client.generate_text(url, payload))
                assistant_message = "".join(assistant_message)
                print("\n")
            else:
                result = asyncio.run(client.generate_text(url, payload))
                assistant_message = result["output"]
                sys.stdout.write(assistant_message + "\n")

            messages.append({"role": "assistant", "content": assistant_message})


        except Exception as e:
            print("\n")
            logger.error(e)
            traceback.print_exc()

        i += 1
    # console.end_capture()



if __name__ == "__main__":
    asyncio.run(main())
