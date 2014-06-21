import sys

assert sys.version >= '3.3', 'Please use Python 3.3 or higher.'
import asyncio

from flask import Flask

from proxy.cmd_line import CmdLine
from .gs_proxy import init_proxy
from .web_server import init_web_server
from .urls import flask_route

from .manager import Manager
from .ws_server import websocket_serve


def run():
    loop = asyncio.get_event_loop()
    server = None
    cmd_line = CmdLine()

    # main task to initialize everything
    manager = Manager(cmd_line=cmd_line)

    task_game_proxy = asyncio.Task(init_proxy(loop, manager))

    flask_app = flask_route(loop, manager)
    task_web_server = asyncio.Task(init_web_server(flask_app, loop))

    task_websocket = asyncio.Task(websocket_serve(loop, manager))

    # run
    try:
        server = loop.run_forever()
    except KeyboardInterrupt:
        print("exit")
    except:
        print("killed")
    finally:
        task_game_proxy.close()
        task_web_server.close()
        task_websocket.close()
        loop.close()


if __name__ == '__main__':
    run()
