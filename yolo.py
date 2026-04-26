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

# Публикация обработанного изображения и координат объектов
mask_pub = rospy.Publisher('~mask', Image, queue_size=1)
point_pub = rospy.Publisher('~detected_object', PointStamped, queue_size=10)

model = YOLO('/home/clover/best.pt')


colors = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255),
    (255, 0, 255), (192, 192, 192), (128, 128, 128), (128, 0, 0), (128, 128, 0),
    (0, 128, 0), (128, 0, 128), (0, 128, 128), (0, 0, 128), (72, 61, 139),
    (47, 79, 79), (47, 79, 47), (0, 206, 209), (148, 0, 211), (255, 20, 147)
]


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

@long_callback
def image_callback(msg):
    global class_name
    img = bridge.imgmsg_to_cv2(msg, 'bgr8')

    # --- Детекция YOLO ---
    results = model(img, verbose=False)
    for result in results:
        # Получение данных об объектах
        classes_names = result.names
        classes = result.boxes.cls.cpu().numpy()
        boxes = result.boxes.xyxy.cpu().numpy().astype(np.int32)
        # Рисование рамок и подписей на кадре
        for class_id, box, conf in zip(classes, boxes, result.boxes.conf):
            if conf>0.5:
                class_name = classes_names[int(class_id)]
                color = colors[int(class_id) % len(colors)]
                x1, y1, x2, y2 = box
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                cv2.putText(img, class_name, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


    # Публикация изображения с аннотациями
    if mask_pub.get_num_connections() > 0:
        mask_pub.publish(bridge.cv2_to_imgmsg(img, 'bgr8'))

# Подписка на топик камеры
image_sub = rospy.Subscriber('main_camera/image_raw', Image, image_callback, queue_size=1)


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
if class_name == 'brakonier':
    navigate_wait()
navigate_wait(x=0, y=0, z=1, frame_id='aruco_map')
land()
rospy.sleep(3)