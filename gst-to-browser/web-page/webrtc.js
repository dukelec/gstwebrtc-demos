/* vim: set sts=4 sw=4 et :
 *
 * Demo Javascript app for negotiating and streaming a sendrecv webrtc stream
 * with a GStreamer app. Runs only in passive mode, i.e., responds to offers
 * with answers, exchanges ICE candidates, and streams.
 *
 * Author: Nirbheek Chauhan <nirbheek@centricular.com>
 * Simplify by: Duke Fong <duke@dukelec.com>
 */

// Override with your own STUN servers if you want
var rtc_conf = {iceServers: [{urls: "stun:stun.services.mozilla.com"},
                             {urls: "stun:stun.l.google.com:19302"}]};
var rtc_pc;
var ws;


function websocketServerConnect() {

    var ws_url = 'ws://' + window.location.hostname + ':8443/browser'
    
    console.log("Connecting to server " + ws_url);
    ws = new WebSocket(ws_url);
    
    ws.onopen = function(evt) {
        ws.send('IS_GST_ONLINE');
        console.log("send: IS_GST_ONLINE");
    }
    
    ws.onmessage = function(evt) {
        console.log("Received " + evt.data);
        switch (evt.data) {
        case "YES_GST_ONLINE":
            ws.send('START_WEBRTC');
            console.log("send: START_WEBRTC");
            return;
        
        default:
            msg = JSON.parse(event.data);

            // Incoming JSON signals the beginning of a call
            if (!rtc_pc)
                createCall(msg);

            if (msg.sdp != null) {
                var sdp = msg.sdp;
                rtc_pc.setRemoteDescription(sdp).then(() => {
                    console.log("Remote SDP set");
                    if (sdp.type != "offer")
                        return;
                    console.log("Got SDP offer");
                    rtc_pc.createAnswer().then((desc) => {
                        console.log("Got local description: " + JSON.stringify(desc));
                        rtc_pc.setLocalDescription(desc).then(function() {
                            console.log("Sending SDP answer");
                            ws.send(JSON.stringify({'sdp': rtc_pc.localDescription}));
                        });
                    });
                });
            } else if (msg.ice != null) {
                var candidate = new RTCIceCandidate(msg.ice);
                rtc_pc.addIceCandidate(candidate);
            } else {
                console.error("Unknown incoming JSON: " + msg);
            }
        }
    }
    
    ws.onerror = function(evt) {
        console.log("ws onerror: ", evt);
    }
    
    ws.onclose = function(evt) {
        console.log('disconnected');
    }
}


function createCall(msg) {

    console.log('Creating RTCPeerConnection');

    rtc_pc = new RTCPeerConnection(rtc_conf);
    
    rtc_pc.ontrack = (event) => {
        if (document.getElementById("stream").srcObject)
            return;
        console.log('streams array length: ', event.streams.length);
        document.getElementById("stream").srcObject = event.streams[0];
    };

    if (!msg.sdp) {
        console.log("WARNING: First message wasn't an SDP message!?");
    }
    
    rtc_pc.onnegotiationneeded = () => {
        console.log("rtc_pc.onnegotiationneeded callback.");
    };

    rtc_pc.onicecandidate = (event) => {
        // We have a candidate, send it to the remote party with the same uuid
        if (event.candidate == null) {
            console.log("ICE Candidate was null, done");
            return;
        }
        ws.send(JSON.stringify({'ice': event.candidate}));
    };
}
