import cv2
import os

video_path = 'flight_video.avi'
output_dir = 'dataset_frames'
os.makedirs(output_dir, exist_ok=True)

cap = cv2.VideoCapture(video_path)
frame_count = 0
saved_count = 0
save_interval = 30  # Сохранять каждый 30-й кадр

while True:
    ret, frame = cap.read()
    if not ret:
        break
        
    if frame_count % save_interval == 0:
        frame_name = os.path.join(output_dir, f'frame_{saved_count:05d}.jpg')
        cv2.imwrite(frame_name, frame)
        saved_count += 1
        
    frame_count += 1

cap.release()
print(f"Сохранено {saved_count} кадров в папку '{output_dir}'")