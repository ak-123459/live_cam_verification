import numpy as np
import cv2

def estimate_pose_from_kps(kps, image_size):
    model_points = np.array([
        [0.0,    0.0,    0.0  ],   # nose tip
        [-30.0, -30.0, -30.0 ],   # left eye
        [30.0,  -30.0, -30.0 ],   # right eye
        [-25.0,  25.0, -30.0 ],   # left mouth
        [25.0,   25.0, -30.0 ],   # right mouth
    ], dtype=np.float64)

    image_points = np.array([
        kps[2],   # nose tip
        kps[0],   # left eye
        kps[1],   # right eye
        kps[3],   # left mouth
        kps[4],   # right mouth
    ], dtype=np.float64)

    focal         = image_size
    center        = (image_size / 2, image_size / 2)
    camera_matrix = np.array([
        [focal, 0,     center[0]],
        [0,     focal, center[1]],
        [0,     0,     1        ]
    ], dtype=np.float64)
    dist_coeffs = np.zeros((4, 1))

    success, rvec, tvec = cv2.solvePnP(
        model_points, image_points,
        camera_matrix, dist_coeffs,
        flags=cv2.SOLVEPNP_EPNP   # ← FIX: EPNP works with 4+ points, ITERATIVE needs 6+
    )

    if not success:
        return None, None, None

    rmat, _ = cv2.Rodrigues(rvec)
    sy       = np.sqrt(rmat[0,0]**2 + rmat[1,0]**2)
    singular = sy < 1e-6

    if not singular:
        pitch = np.arctan2( rmat[2,1], rmat[2,2])
        yaw   = np.arctan2(-rmat[2,0], sy)
        roll  = np.arctan2( rmat[1,0], rmat[0,0])
    else:
        pitch = np.arctan2(-rmat[1,2], rmat[1,1])
        yaw   = np.arctan2(-rmat[2,0], sy)
        roll  = 0

    return np.degrees(yaw), np.degrees(pitch), np.degrees(roll)