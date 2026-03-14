import cv2
import sys
import socket

# ─────────────────────────────────────────────
#  CONFIG — change IP/port to match your phone
# ─────────────────────────────────────────────
CAMERA_IP   = "10.153.70.148"   # ← update this
CAMERA_PORT = 8080
# Common stream paths to auto-try
STREAM_PATHS = [
    "/video",
    "/videofeed",
    "/mjpeg",
    "/stream",
    "/live",
    "/?action=stream",
]
# ─────────────────────────────────────────────


def check_host_reachable(ip, port, timeout=2):
    try:
        sock = socket.create_connection((ip, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def find_working_stream(ip, port):
    print(f"\n🔍 Scanning http://{ip}:{port} for working stream...\n")
    for path in STREAM_PATHS:
        url = f"http://{ip}:{port}{path}"
        print(f"  Trying: {url} ...", end=" ", flush=True)
        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                print("✅ WORKS!")
                cap.release()
                return url
            cap.release()
        print("❌")
    return None


def stream_camera(url):
    print(f"\n🎥 Connecting to: {url}")
    print("   Press  Q  to quit\n")

    cap = cv2.VideoCapture(url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # reduce latency

    if not cap.isOpened():
        print(f"❌ Could not open stream: {url}")
        sys.exit(1)

    print("✅ Stream opened! Displaying feed...\n")

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️  Frame read failed — reconnecting...")
            cap.release()
            cap = cv2.VideoCapture(url)
            continue

        frame_count += 1
        h, w = frame.shape[:2]

        # Overlay info on frame
        cv2.putText(frame, f"Source: {url}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)
        cv2.putText(frame, f"Frame: {frame_count}  |  {w}x{h}", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)

        cv2.imshow("Camera Stream — press Q to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\n👋 Quit by user.")
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # Allow passing IP as argument: python camera_connect.py 192.168.1.5
    ip   = sys.argv[1] if len(sys.argv) > 1 else CAMERA_IP
    port = int(sys.argv[2]) if len(sys.argv) > 2 else CAMERA_PORT

    print(f"📡 Checking if {ip}:{port} is reachable...")
    if not check_host_reachable(ip, port):
        print(f"\n❌ Cannot reach {ip}:{port}")
        print("   • Is the camera app running on the phone?")
        print("   • Are both devices on the same WiFi?")
        print(f"   • Try opening  http://{ip}:{port}/  in your browser first")
        sys.exit(1)

    print(f"✅ Host reachable!")

    # Auto-detect working stream path
    working_url = find_working_stream(ip, port)

    if not working_url:
        print("\n❌ No working stream path found.")
        print(f"   Open http://{ip}:{port}/ in browser to see available paths.")
        sys.exit(1)

    stream_camera(working_url)