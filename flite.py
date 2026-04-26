#!/usr/bin/env python3
import rospy
import cv2
import numpy as np
from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import PointStamped
from std_msgs.msg import String
from cv_bridge import CvBridge
from clover import long_callback, srv
import tf2_ros
import tf2_geometry_msgs
import image_geometry
import math
from std_srvs.srv import Trigger
import time
from ultralytics import YOLO

rospy.init_node('cv_mission_yolo')

# Сервисы Clover
get_telemetry = rospy.ServiceProxy('get_telemetry', srv.GetTelemetry)
navigate = rospy.ServiceProxy('navigate', srv.Navigate)
set_position = rospy.ServiceProxy('set_position', srv.SetPosition)
land = rospy.ServiceProxy('land', Trigger)

bridge = CvBridge()

# TF и модель камеры
tf_buffer = tf2_ros.Buffer()
tf_listener = tf2_ros.TransformListener(tf_buffer)
camera_model = image_geometry.PinholeCameraModel()
camera_model.fromCameraInfo(rospy.wait_for_message('main_camera/camera_info', CameraInfo))

# Публикация обработанного изображения и координат объектов
mask_pub = rospy.Publisher('~mask', Image, queue_size=1)
point_pub = rospy.Publisher('~detected_object', PointStamped, queue_size=10)

# Загрузка обученной модели YOLO
MODEL_PATH = '/home/clover/best.pt'
model = YOLO(MODEL_PATH)
CONFIDENCE_THRESHOLD = 0.5

# Глобальные переменные для записи видео
video_writer = None
recording = False
screen = None

# Словарь с целевыми координатами объектов (известные позиции на карте)
TARGET_OBJECTS = {
    'brakonier': (0.0, 0.5),      # топор
    'gribnik': (0.5, 0.0), # гриб
    'tyrist': (1.5, 0.0)  # рюкзак
}

def navigate_wait(x=0, y=0, z=1, speed=0.5, frame_id='aruco_map', tolerance=0.2, auto_arm=False):
    """Полет в точку с ожиданием прибытия."""
    res = navigate(x=x, y=y, z=z, speed=speed, frame_id=frame_id, auto_arm=auto_arm)
    if not res.success:
        return res
    while not rospy.is_shutdown():
        telem = get_telemetry(frame_id='navigate_target')
        if math.sqrt(telem.x**2 + telem.y**2 + telem.z**2) < tolerance:
            return res
        rospy.sleep(0.2)

def start_video_recording(output_path='flight_video.avi', fps=15.0, frame_size=(320, 240)):
    """Инициализация записи видео."""
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    out = cv2.VideoWriter(output_path, fourcc, fps, frame_size)
    if not out.isOpened():
        rospy.logerr("Не удалось открыть VideoWriter!")
        return None
    return out

def pixel_to_map(u, v, camera_model, tf_buffer, target_frame='aruco_map'):
    """
    Преобразование координат пикселя (u,v) в точку на плоскости земли (z=0) в системе target_frame.
    Используется модель камеры и tf-трансформация.
    """
    # Луч из камеры через пиксель
    ray = camera_model.projectPixelTo3dRay((u, v))
    ray = np.array(ray)

    # Нормализуем луч
    ray = ray / np.linalg.norm(ray)

    # Вычисляем точку пересечения луча с плоскостью земли (z = высота камеры от земли)
    # Получаем положение камеры в карте
    try:
        transform = tf_buffer.lookup_transform(target_frame, camera_model.tf_frame, rospy.Time(0), rospy.Duration(1.0))
    except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException) as e:
        rospy.logwarn(f"TF lookup failed: {e}")
        return None

    cam_pos = np.array([transform.transform.translation.x,
                        transform.transform.translation.y,
                        transform.transform.translation.z])

    # Плоскость земли: z = 0
    # Уравнение луча: P = cam_pos + t * ray_direction
    # Найдем t, при котором z = 0
    if abs(ray[2]) < 1e-6:
        return None  # Луч параллелен земле

    t = -cam_pos[2] / ray[2]
    if t < 0:
        return None  # Пересечение позади камеры

    intersection = cam_pos + t * ray
    return intersection[:2]  # (x, y)

@long_callback
def image_callback(msg):
    global screen, video_writer, recording

    img = bridge.imgmsg_to_cv2(msg, 'bgr8')
    screen = img

    # --- Детекция YOLO ---
    results = model(img, verbose=False)

    # Обработка результатов
    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                conf = float(box.conf[0])
                if conf < CONFIDENCE_THRESHOLD:
                    continue

                cls_id = int(box.cls[0])
                class_name = model.names[cls_id]
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                # Центр рамки
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                # Преобразование в координаты карты
                map_xy = pixel_to_map(cx, cy, camera_model, tf_buffer, 'aruco_map')
                if map_xy is not None:
                    # Публикуем точку в топик
                    point_msg = PointStamped()
                    point_msg.header.stamp = rospy.Time.now()
                    point_msg.header.frame_id = 'aruco_map'
                    point_msg.point.x = map_xy[0]
                    point_msg.point.y = map_xy[1]
                    point_msg.point.z = 0.0
                    point_pub.publish(point_msg)

                    rospy.loginfo(f"Detected {class_name} at map coordinates: ({map_xy[0]:.2f}, {map_xy[1]:.2f})")

                # Отрисовка на изображении
                label = f"{class_name} {conf:.2f}"
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Запись видео
    if recording and video_writer is not None:
        video_writer.write(img)

    # Публикация изображения с аннотациями
    if mask_pub.get_num_connections() > 0:
        mask_pub.publish(bridge.cv2_to_imgmsg(img, 'bgr8'))

# Подписка на топик камеры
image_sub = rospy.Subscriber('main_camera/image_raw', Image, image_callback, queue_size=1)

# ===== Полётная программа =====
if __name__ == '__main__':
    try:
        # Ожидание первого кадра для инициализации видео
        rospy.loginfo("Waiting for first frame...")
        first_msg = rospy.wait_for_message('main_camera/image_raw', Image)
        first_frame = bridge.imgmsg_to_cv2(first_msg, 'bgr8')
        height, width = first_frame.shape[:2]
        rospy.loginfo(f"Camera resolution: {width}x{height}")

        # Запуск записи видео
        video_writer = start_video_recording(
            output_path='flight_video.avi',
            fps=15.0,
            frame_size=(width, height)
        )
        if video_writer is not None:
            recording = True
            rospy.loginfo("Video recording started")
        else:
            rospy.logwarn("Video recording failed, continuing without video")

        # Взлет
        navigate_wait(x=0, y=0, z=1.6, frame_id='body', auto_arm=True)

        # Облет целевых точек для осмотра объектов
        # Можно заменить на последовательный облет известных позиций
        inspection_points = [
            (0.0, 0.5, 0.8),  # над топором
            (0.5, 0.0, 0.8),  # над грибом
            (-0.5, 0.0, 0.8)   # над рюкзаком
        ]

        for x, y, z in inspection_points:
            navigate_wait(x=x, y=y, z=z, frame_id='aruco_map')
            rospy.sleep(2)  # даем время на детекцию
            # Здесь можно добавить логику: если объект обнаружен, выполнить действие
            # Например, приземлиться рядом или зависнуть над ним

        # Возврат и посадка
        navigate_wait(x=0, y=0, z=1, frame_id='aruco_map')
        land()
        rospy.sleep(3)

    except rospy.ROSInterruptException:
        pass
    finally:
        recording = False
        if video_writer is not None:
            video_writer.release()
            rospy.loginfo("Video saved")
        rospy.spin()