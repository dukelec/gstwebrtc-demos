#!/usr/bin/env python3

import asyncio
import datetime
import random
import websockets

gst_ws = None
browser_ws = None

async def time(websocket, path):
    global gst_ws
    global browser_ws
    
    if path == '/gst':
        try:
            gst_ws = websocket
            print('gst connected')
            while True:
                data = await gst_ws.recv()
                print('gst -> browser: ' + data)
                if browser_ws:
                    await browser_ws.send(data)
                else:
                    print('skip because browser offline')
        except websockets.exceptions.ConnectionClosed:
            print('gst disconnect')
            gst_ws = None
    
    if path == '/browser':
        try:
            browser_ws = websocket
            print('browser connected')
            while True:
                data = await browser_ws.recv()
                print('browser -> gst: ' + data)
                if gst_ws:
                    await gst_ws.send(data)
                else:
                    print('skip because gst offline')
        except websockets.exceptions.ConnectionClosed:
            print('browser disconnected')
            browser_ws = None
    
    else:
        print('unsupport path, exit...')


start_server = websockets.serve(time, '0.0.0.0', 8443)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
