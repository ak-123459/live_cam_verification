# pip install insightface
# pip install onnxruntime


import cv2
from insightface.app import FaceAnalysis

app = FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=0)  # Use 0 for CPU, >0 for GPU

img = cv2.imread("/mnt/data/face-right.jpg")
faces = app.get(img)

if faces:
    face = faces[0]
    print("Pose (yaw, pitch, roll):", face.pose)  # Direct face angle
    print("Bounding Box:", face.bbox)

    # Draw bounding box
    x1, y1, x2, y2 = map(int, face.bbox)
    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

    cv2.putText(img, f"Yaw: {face.pose[0]:.2f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    cv2.putText(img, f"Pitch: {face.pose[1]:.2f}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    cv2.putText(img, f"Roll: {face.pose[2]:.2f}", (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    cv2.imshow("Detected Face", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
else:
    print("No face detected.")
