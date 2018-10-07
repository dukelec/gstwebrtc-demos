#!/usr/bin/env python3

import random
import ssl
import websockets
import asyncio
import os
import sys
import json
import argparse

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

#PIPELINE_DESC = '''
#webrtcbin name=sendrecv
# v4l2src ! video/x-raw,width=320,height=240 ! videoconvert ! queue ! vp8enc deadline=1 ! rtpvp8pay !
# queue ! application/x-rtp,media=video,encoding-name=VP8,payload=97 ! sendrecv.
#'''

PIPELINE_DESC = '''
webrtcbin name=sendrecv
 videotestsrc pattern=ball ! video/x-raw,width=320,height=240 ! videoconvert ! queue ! vp8enc deadline=1 ! rtpvp8pay !
 queue ! application/x-rtp,media=video,encoding-name=VP8,payload=97 ! sendrecv.
'''

class WebRTCClient:
    def __init__(self, ws_url):
        self.ws = None
        self.pipe = None
        self.webrtc = None
        self.ws_url = ws_url or 'ws://localhost:8443/gst'


    def send_sdp_offer(self, offer):
        text = offer.sdp.as_text()
        print('sending offer:\n%s' % text)
        msg = json.dumps({'sdp': {'type': 'offer', 'sdp': text}})
        asyncio.new_event_loop().run_until_complete(self.ws.send(msg))

    def on_offer_created(self, promise, _, __):
        promise.wait()
        reply = promise.get_reply()
        offer = reply['offer']
        promise = Gst.Promise.new()
        self.webrtc.emit('set-local-description', offer, promise)
        promise.interrupt()
        self.send_sdp_offer(offer)

    def on_negotiation_needed(self, element):
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, element, None)
        element.emit('create-offer', None, promise)

    def send_ice_candidate_message(self, _, mlineindex, candidate):
        icemsg = json.dumps({'ice': {'candidate': candidate, 'sdpMLineIndex': mlineindex}})
        asyncio.new_event_loop().run_until_complete(self.ws.send(icemsg))



    async def handle_sdp(self, message):
        assert (self.webrtc)
        msg = json.loads(message)
        if 'sdp' in msg:
            sdp = msg['sdp']
            assert(sdp['type'] == 'answer')
            sdp = sdp['sdp']
            print ('received answer:\n%s' % sdp)
            res, sdpmsg = GstSdp.SDPMessage.new()
            GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
            answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
            promise = Gst.Promise.new()
            self.webrtc.emit('set-remote-description', answer, promise)
            promise.interrupt()
        elif 'ice' in msg:
            ice = msg['ice']
            candidate = ice['candidate']
            sdpmlineindex = ice['sdpMLineIndex']
            self.webrtc.emit('add-ice-candidate', sdpmlineindex, candidate)

    def start_pipeline(self):
        self.pipe = Gst.parse_launch(PIPELINE_DESC)
        self.webrtc = self.pipe.get_by_name('sendrecv')
        self.webrtc.connect('on-negotiation-needed', self.on_negotiation_needed)
        self.webrtc.connect('on-ice-candidate', self.send_ice_candidate_message)
        #self.webrtc.connect('pad-added', self.on_incoming_stream)
        self.pipe.set_state(Gst.State.PLAYING)


    async def loop(self):
        assert self.ws
        async for message in self.ws:
            if message == 'IS_GST_ONLINE':
                await self.ws.send('YES_GST_ONLINE')
            elif message == 'START_WEBRTC':
                self.start_pipeline()
            else:
                await self.handle_sdp(message)
        return 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url)
        print("ws connected")


def check_plugins():
    needed = ["opus", "vpx", "nice", "webrtc", "dtls", "srtp", "rtp",
              "rtpmanager", "videotestsrc", "audiotestsrc"]
    missing = list(filter(lambda p: Gst.Registry.get().find_plugin(p) is None, needed))
    if len(missing):
        print('missing gstreamer plugins:', missing)
        sys.exit(1)

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ws-url', help='Signalling server to connect to, eg "ws://127.0.0.1:8443/gst"')
    args = parser.parse_args()
    
    Gst.init(None)
    check_plugins()
    c = WebRTCClient(args.ws_url)
    asyncio.get_event_loop().run_until_complete(c.connect())
    asyncio.get_event_loop().run_until_complete(c.loop())

