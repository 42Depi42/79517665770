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
from pyzbar import pyzbar

rospy.init_node('cv_mission')
bridge = CvBridge()
get_telemetry = rospy.ServiceProxy('get_telemetry', srv.GetTelemetry)
navigate = rospy.ServiceProxy('navigate', srv.Navigate)
set_position = rospy.ServiceProxy('set_position', srv.SetPosition)
land = rospy.ServiceProxy('land', Trigger)
tf_buffer = tf2_ros.Buffer()
tf_listener = tf2_ros.TransformListener(tf_buffer)
camera_model = image_geometry.PinholeCameraModel()
camera_model.fromCameraInfo(rospy.wait_for_message('main_camera/camera_info', CameraInfo))

# Публикация
mask_pub = rospy.Publisher('~mask', Image, queue_size=1)
point_pub = rospy.Publisher('~detected_object', PointStamped, queue_size=1)

# Глобальная переменная для VideoWriter
video_writer = None
recording = False  # Флаг, управляющий записью
def navigate_wait(x=0, y=0, z=1.8, speed=0.5, frame_id='aruco_map', tolerance=0.2, auto_arm=False):
    res = navigate(x=x, y=y, z=z, speed=speed, frame_id=frame_id, auto_arm=auto_arm)
    if not res.success:
        return res
    while not rospy.is_shutdown():
        telem = get_telemetry(frame_id='navigate_target')
        if math.sqrt(telem.x ** 2 + telem.y ** 2 + telem.z ** 2) < tolerance:
            return res
        rospy.sleep(0.2)
        
def start_video_recording(output_path='/home/pi/flight_video.avi', fps=20.0, frame_size=(640, 480)):
    """
    Инициализация записи видео.
    :param output_path: путь к сохраняемому файлу
    :param fps: желаемая частота кадров (можно подстроить под реальную частоту камеры)
    :param frame_size: разрешение кадра (ширина, высота)
    :return: объект VideoWriter
    """
    # Кодек: 'XVID' для .avi, 'mp4v' для .mp4 (если установлен ffmpeg)
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_path, fourcc, fps, frame_size)
    if not out.isOpened():
        rospy.logerr("Не удалось открыть VideoWriter!")
        return None
    return out

@long_callback
def image_callback(msg):
    global screen, video_writer, recording

    img = bridge.imgmsg_to_cv2(msg, 'bgr8')
    screen = img  # сохраняем последний кадр (для возможных скриншотов)

    # --- Обработка изображения (поиск фигур и QR) ---
    img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # --- Запись кадра в видео, если идёт запись ---
    if recording and video_writer is not None:
        video_writer.write(img)

    # Публикация маски (как и раньше)
    if mask_pub.get_num_connections() > 0:
        mask_pub.publish(bridge.cv2_to_imgmsg(img, 'bgr8'))

# ... функции navigate_wait, detected_shapes, detected_qr без изменений ...

image_sub = rospy.Subscriber('main_camera/image_raw', Image, image_callback, queue_size=1)

# ===== Полётная программа с записью видео =====

try:
    # Определяем разрешение кадра (можно взять из первого полученного кадра или задать вручную)
    # Для надёжности ждём первый кадр, чтобы узнать его размер
    rospy.loginfo("Ожидание первого кадра для определения разрешения...")
    first_msg = rospy.wait_for_message('main_camera/image_raw', Image)
    first_frame = bridge.imgmsg_to_cv2(first_msg, 'bgr8')
    height, width = first_frame.shape[:2]
    rospy.loginfo(f"Разрешение камеры: {width}x{height}")

    # Запускаем запись видео
    video_writer = start_video_recording(
        output_path='flight_video.avi',
        fps=15.0,               # можно подобрать под частоту публикации топика
        frame_size=(width, height)
    )
    recording = True
    rospy.loginfo("Запись видео начата")

    # Теперь выполняем полёт
    navigate_wait(x=0, y=0, z=0.8, frame_id='body', auto_arm=True)
    navigate_wait(x=1, z=0.8)
    navigate_wait(x=1, z=0.8)
    navigate_wait(x=0, z=0.8)
    navigate_wait(y=1, z=0.8)
    navigate_wait(x=-0.5, z=1)
    navigate_wait(z=0.8)

    land()
    rospy.sleep(3)  # даём время на запись последних кадров

finally:
    # Останавливаем запись видео в любом случае
    recording = False
    if video_writer is not None:
        video_writer.release()
        rospy.loginfo("Запись видео остановлена, файл сохранён")

rospy.spin()