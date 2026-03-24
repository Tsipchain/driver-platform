import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import '../../services/webrtc_service.dart';

class VideoCallScreen extends StatefulWidget {
  const VideoCallScreen({super.key});

  @override
  State<VideoCallScreen> createState() => _VideoCallScreenState();
}

class _VideoCallScreenState extends State<VideoCallScreen> {
  final _webrtc = WebRTCService();
  final _localRenderer = RTCVideoRenderer();
  final _remoteRenderer = RTCVideoRenderer();
  String _callState = 'idle';
  bool _audioEnabled = true;
  bool _videoEnabled = true;

  @override
  void initState() {
    super.initState();
    _initRenderers();
  }

  Future<void> _initRenderers() async {
    await _localRenderer.initialize();
    await _remoteRenderer.initialize();

    _webrtc.onLocalStream = (stream) {
      setState(() => _localRenderer.srcObject = stream);
    };
    _webrtc.onRemoteStream = (stream) {
      setState(() => _remoteRenderer.srcObject = stream);
    };
    _webrtc.onCallState = (state) {
      setState(() => _callState = state);
    };
    _webrtc.onVerificationResult = (result) {
      final status = result['status'] ?? 'unknown';
      final txHash = result['tx_hash'];
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Verification: $status${txHash != null ? " (TX: ${txHash.toString().substring(0, 12)}...)" : ""}')),
      );
    };
  }

  Future<void> _startCall() async {
    setState(() => _callState = 'connecting');
    await _webrtc.connect('driver_${DateTime.now().millisecondsSinceEpoch}');
    await _webrtc.startCall('call_${DateTime.now().millisecondsSinceEpoch}');
  }

  Future<void> _endCall() async {
    await _webrtc.dispose();
    setState(() {
      _callState = 'idle';
      _localRenderer.srcObject = null;
      _remoteRenderer.srcObject = null;
    });
  }

  @override
  void dispose() {
    _webrtc.dispose();
    _localRenderer.dispose();
    _remoteRenderer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('VerifyID Call Agent'),
        backgroundColor: Colors.black87,
      ),
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Remote video (full screen)
          if (_callState == 'in_call')
            Positioned.fill(
              child: RTCVideoView(_remoteRenderer, objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover),
            )
          else
            Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.video_call, size: 80, color: Colors.white.withOpacity(0.3)),
                  const SizedBox(height: 16),
                  Text(
                    _callState == 'connecting' ? 'Connecting to agent...' : 'Call VerifyID Agent',
                    style: const TextStyle(color: Colors.white70, fontSize: 18),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'WebRTC video supervision for drone deliveries\nand driver identity verification',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.white38, fontSize: 14),
                  ),
                  if (_callState == 'connecting') ...[
                    const SizedBox(height: 24),
                    const CircularProgressIndicator(color: Colors.white54),
                  ],
                ],
              ),
            ),

          // Local video (PiP)
          if (_callState == 'in_call' || _callState == 'connecting')
            Positioned(
              right: 16,
              top: 16,
              width: 120,
              height: 160,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Container(
                  color: Colors.grey.shade900,
                  child: RTCVideoView(_localRenderer, mirror: true, objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover),
                ),
              ),
            ),

          // Controls
          Positioned(
            bottom: 40,
            left: 0,
            right: 0,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (_callState == 'in_call') ...[
                  _CallButton(
                    icon: _audioEnabled ? Icons.mic : Icons.mic_off,
                    color: _audioEnabled ? Colors.white24 : Colors.red,
                    onTap: () {
                      setState(() => _audioEnabled = !_audioEnabled);
                      _webrtc.toggleAudio(_audioEnabled);
                    },
                  ),
                  const SizedBox(width: 20),
                ],
                _CallButton(
                  icon: _callState == 'idle' ? Icons.call : Icons.call_end,
                  color: _callState == 'idle' ? Colors.green : Colors.red,
                  size: 64,
                  onTap: _callState == 'idle' ? _startCall : _endCall,
                ),
                if (_callState == 'in_call') ...[
                  const SizedBox(width: 20),
                  _CallButton(
                    icon: _videoEnabled ? Icons.videocam : Icons.videocam_off,
                    color: _videoEnabled ? Colors.white24 : Colors.red,
                    onTap: () {
                      setState(() => _videoEnabled = !_videoEnabled);
                      _webrtc.toggleVideo(_videoEnabled);
                    },
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CallButton extends StatelessWidget {
  final IconData icon;
  final Color color;
  final double size;
  final VoidCallback onTap;

  const _CallButton({required this.icon, required this.color, this.size = 52, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(shape: BoxShape.circle, color: color),
        child: Icon(icon, color: Colors.white, size: size * 0.45),
      ),
    );
  }
}
