import 'dart:convert';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config/app_config.dart';

class WebRTCService {
  WebSocketChannel? _channel;
  RTCPeerConnection? _peerConnection;
  MediaStream? _localStream;
  MediaStream? _remoteStream;
  String? _callId;
  String? _userId;

  Function(MediaStream)? onLocalStream;
  Function(MediaStream)? onRemoteStream;
  Function(String)? onCallState;
  Function(Map<String, dynamic>)? onVerificationResult;

  static const _iceServers = {
    'iceServers': [
      {'urls': 'stun:stun.l.google.com:19302'},
      {'urls': 'stun:stun1.l.google.com:19302'},
    ]
  };

  Future<void> connect(String userId) async {
    _userId = userId;
    final wsUrl = '${AppConfig.wsEndpoint}/$userId';
    _channel = WebSocketChannel.connect(Uri.parse(wsUrl));

    _channel!.stream.listen(
      (message) => _handleMessage(jsonDecode(message)),
      onError: (e) => onCallState?.call('error'),
      onDone: () => onCallState?.call('disconnected'),
    );
  }

  Future<void> startCall(String callId) async {
    _callId = callId;
    _localStream = await navigator.mediaDevices.getUserMedia({
      'audio': true,
      'video': {'facingMode': 'user'},
    });
    onLocalStream?.call(_localStream!);

    _peerConnection = await createPeerConnection(_iceServers);

    _localStream!.getTracks().forEach((track) {
      _peerConnection!.addTrack(track, _localStream!);
    });

    _peerConnection!.onTrack = (event) {
      if (event.streams.isNotEmpty) {
        _remoteStream = event.streams[0];
        onRemoteStream?.call(_remoteStream!);
      }
    };

    _peerConnection!.onIceCandidate = (candidate) {
      _send({
        'type': 'ice_candidate',
        'candidate': candidate.toMap(),
      });
    };

    // Join call room
    _send({'type': 'join_call', 'call_id': callId});
    onCallState?.call('connecting');
  }

  Future<void> _handleMessage(Map<String, dynamic> msg) async {
    switch (msg['type']) {
      case 'new_peer':
        // Create and send offer
        final offer = await _peerConnection!.createOffer();
        await _peerConnection!.setLocalDescription(offer);
        _send({
          'type': 'offer',
          'sdp': offer.sdp,
          'sdp_type': offer.type,
        });
        break;

      case 'offer':
        await _peerConnection!.setRemoteDescription(
          RTCSessionDescription(msg['sdp'], msg['sdp_type'] ?? 'offer'),
        );
        final answer = await _peerConnection!.createAnswer();
        await _peerConnection!.setLocalDescription(answer);
        _send({
          'type': 'answer',
          'sdp': answer.sdp,
          'sdp_type': answer.type,
        });
        onCallState?.call('in_call');
        break;

      case 'answer':
        await _peerConnection!.setRemoteDescription(
          RTCSessionDescription(msg['sdp'], msg['sdp_type'] ?? 'answer'),
        );
        onCallState?.call('in_call');
        break;

      case 'ice_candidate':
        final candidateMap = msg['candidate'];
        if (candidateMap != null) {
          await _peerConnection!.addCandidate(RTCIceCandidate(
            candidateMap['candidate'],
            candidateMap['sdpMid'],
            candidateMap['sdpMLineIndex'],
          ));
        }
        break;

      case 'verification_result':
        onVerificationResult?.call(msg);
        onCallState?.call('completed');
        break;

      case 'peer_left':
        onCallState?.call('peer_left');
        break;
    }
  }

  void _send(Map<String, dynamic> data) {
    data['from'] = _userId;
    _channel?.sink.add(jsonEncode(data));
  }

  void toggleAudio(bool enabled) {
    _localStream?.getAudioTracks().forEach((track) {
      track.enabled = enabled;
    });
  }

  void toggleVideo(bool enabled) {
    _localStream?.getVideoTracks().forEach((track) {
      track.enabled = enabled;
    });
  }

  Future<void> dispose() async {
    _localStream?.getTracks().forEach((t) => t.stop());
    await _localStream?.dispose();
    await _peerConnection?.close();
    await _channel?.sink.close();
  }
}
