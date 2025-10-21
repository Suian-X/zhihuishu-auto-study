# 智慧树自动刷课脚本
import sys
import time
import json
import traceback
import random
import math
from PIL import ImageGrab
import numpy as np
import pyautogui
from PyQt5 import QtWidgets, QtCore, QtGui

# -------------------- 全局 QApplication --------------------
app = QtWidgets.QApplication(sys.argv)

# -------------------- ROI 选择器 --------------------
class ROIWidget(QtWidgets.QWidget):
    selection_done = QtCore.pyqtSignal(tuple)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Select ROI")
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.showFullScreen()
        self.start_point = None
        self.end_point = None
        self.selection_rect = QtCore.QRect()
        self.overlay_color = QtGui.QColor(0,0,0,120)

    def paintEvent(self,event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.overlay_color)
        if self.start_point and self.end_point:
            rect = self.selection_rect.normalized()
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_Clear)
            painter.fillRect(rect, QtCore.Qt.transparent)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            pen = QtGui.QPen(QtCore.Qt.white,3)
            painter.setPen(pen)
            painter.drawRect(rect)
            font = QtGui.QFont()
            font.setPointSize(12)
            painter.setFont(font)
            painter.setPen(QtCore.Qt.white)
            painter.drawText(rect.topLeft() + QtCore.QPoint(6,-6), f"{rect.width()}x{rect.height()}")

    def mousePressEvent(self,event):
        if event.button()==QtCore.Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.selection_rect = QtCore.QRect(self.start_point,self.end_point)
            self.update()

    def mouseMoveEvent(self,event):
        if self.start_point:
            self.end_point = event.pos()
            self.selection_rect = QtCore.QRect(self.start_point,self.end_point)
            self.update()

    def keyPressEvent(self,event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if self.start_point and self.end_point:
                rect = self.selection_rect.normalized()
                self.selection_done.emit((rect.x(), rect.y(), rect.width(), rect.height()))
            self.close()
        elif event.key()==QtCore.Qt.Key_Escape:
            self.start_point = None
            self.end_point = None
            self.selection_rect = QtCore.QRect()
            self.update()
        elif event.key()==QtCore.Qt.Key_Q:
            self.selection_done.emit(None)
            self.close()

# -------------------- 截图与计算工具 --------------------
def grab_region(region, to_gray=True):
    x,y,w,h = region
    img = ImageGrab.grab(bbox=(x,y,x+w,y+h))
    arr = np.array(img)
    if to_gray:
        from cv2 import cvtColor, COLOR_RGB2GRAY
        return cvtColor(arr, COLOR_RGB2GRAY)
    return arr

def compute_mse(img1,img2):
    if img1.shape != img2.shape:
        h = min(img1.shape[0], img2.shape[0])
        w = min(img1.shape[1], img2.shape[1])
        img1 = img1[:h,:w]
        img2 = img2[:h,:w]
    return float(np.mean((img1.astype("float") - img2.astype("float"))**2))

# -------------------- 人类化鼠标轨迹与安全点击 --------------------
def human_move(x2, y2, duration=0.4):
    """平滑曲线移动鼠标"""
    x1, y1 = pyautogui.position()
    steps = max(8, int(duration * 60))
    for i in range(1, steps+1):
        t = i / steps
        s = 3*t**2 - 2*t**3
        xi = x1 + (x2 - x1) * s + random.uniform(-1.5,1.5)
        yi = y1 + (y2 - y1) * s + random.uniform(-1.5,1.5)
        pyautogui.moveTo(xi, yi, duration=0)
        time.sleep(duration / steps)

def safe_click(x, y, offset=4, hold_time=0.05, move_duration=0.4):
    """模拟人类点击行为"""
    rx = int(x + random.randint(-offset, offset))
    ry = int(y + random.randint(-offset, offset))
    human_move(rx, ry, duration=move_duration)
    pyautogui.mouseDown()
    time.sleep(hold_time + random.uniform(0, 0.05))
    pyautogui.mouseUp()
    # 轻微抖动
    if random.random() < 0.05:
        pyautogui.moveRel(random.uniform(-4,4), random.uniform(-4,4), duration=0.1)

# -------------------- 偶发轻微鼠标移动 --------------------
def small_mouse_drift():
    """偶尔轻微移动鼠标，避免长时间静止"""
    if random.random() < 0.12:  # 12% 概率触发
        x,y = pyautogui.position()
        dx = random.randint(-25,25)
        dy = random.randint(-20,20)
        human_move(x+dx, y+dy, duration=random.uniform(0.2,0.5))

# -------------------- 非阻塞 PyQt 显示 --------------------
class ImageViewer(QtWidgets.QWidget):
    closed = QtCore.pyqtSignal()
    def __init__(self, img, title="截图"):
        super().__init__()
        self.setWindowTitle(title)
        if len(img.shape) == 2:
            h, w = img.shape
            qimg = QtGui.QImage(img.data, w, h, w, QtGui.QImage.Format_Grayscale8)
        elif len(img.shape) == 3:
            h, w, c = img.shape
            qimg = QtGui.QImage(img.data, w, h, 3*w, QtGui.QImage.Format_RGB888)
        else:
            raise ValueError(f"无法显示的图片形状: {img.shape}")
        pixmap = QtGui.QPixmap.fromImage(qimg)
        label = QtWidgets.QLabel(self)
        label.setPixmap(pixmap)
        self.setFixedSize(pixmap.width(), pixmap.height())
        self.show()

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()

def show_image_non_blocking(img, title="截图"):
    viewer = ImageViewer(img, title)
    return viewer

# -------------------- ROI 交互选择 --------------------
def wait_for_user_confirmation(prompt_message):
    print(f"\n{prompt_message}")
    print("   - 鼠标拖拽选择区域")
    print("   - 按 Enter 确认选择")
    print("   - 按 Esc 取消当前选择并重新选择")
    print("   - 按 Q 退出该选择并跳过")
    while True:
        ans = input("请输入 'y' 开始选择，'n' 跳过该区域: ").strip().lower()
        if ans == 'y': return True
        if ans == 'n':
            print("  已跳过该区域")
            return False
        print("  请输入 'y' 或 'n'。")

def select_roi(prompt):
    if not wait_for_user_confirmation(prompt):
        return None
    result_container = {'coords': None}
    def on_done(coords): result_container['coords'] = coords
    widget = ROIWidget()
    widget.selection_done.connect(on_done)
    widget.show()
    while widget.isVisible():
        app.processEvents()
        time.sleep(0.05)
    return result_container['coords']

# -------------------- 自动化逻辑 --------------------
def run_automation(rois, initial_close,
                   check_interval=2.0,
                   video_mse_threshold=1.0,
                   static_required=3,
                   close_mse_threshold=100.0):
    required = ['video_area', 'next_course_area', 'quiz_area', 'close_area']
    for k in required:
        if k not in rois:
            print(f"错误：缺少必要 ROI '{k}'。")
            return

    video_area = (rois['video_area']['x'], rois['video_area']['y'],
                  rois['video_area']['w'], rois['video_area']['h'])
    next_area = (rois['next_course_area']['x'], rois['next_course_area']['y'],
                 rois['next_course_area']['w'], rois['next_course_area']['h'])
    quiz_area = (rois['quiz_area']['x'], rois['quiz_area']['y'],
                 rois['quiz_area']['w'], rois['quiz_area']['h'])
    close_area = (rois['close_area']['x'], rois['close_area']['y'],
                  rois['close_area']['w'], rois['close_area']['h'])

    print("\n进入自动化循环，Ctrl+C 可中断")
    time.sleep(1)
    lessons_done = 0

    while True:
        try:
            # 激活播放
            px = video_area[0] + video_area[2] // 2
            py = video_area[1] + video_area[3] // 2
            safe_click(px, py)
            print("已点击视频区开始播放")

            static_count = 0
            prev_frame = grab_region(video_area, True)

            while True:
                # 随机化检测时间
                jitter = random.uniform(-0.5, 1.0)
                sleep_time = max(0.5, check_interval + jitter)
                time.sleep(sleep_time)

                # 偶尔轻微鼠标移动
                small_mouse_drift()

                curr_frame = grab_region(video_area, True)
                err = compute_mse(prev_frame, curr_frame)
                print(f"  视频区帧差 MSE={err:.3f}")

                if err < video_mse_threshold:
                    static_count += 1
                else:
                    static_count = 0

                prev_frame = curr_frame

                # 检测播放结束或弹题
                if static_count >= static_required:
                    now_close = grab_region(close_area, True)
                    close_mse = compute_mse(initial_close, now_close)
                    print(f"  关闭区 MSE={close_mse:.3f}")

                    if close_mse > close_mse_threshold:
                        print("  视频播放完成 -> 点击下一课")
                        nx = next_area[0] + next_area[2] // 2
                        ny = next_area[1] + next_area[3] // 2
                        safe_click(nx, ny)
                        lessons_done += 1
                        print(f"  已完成 {lessons_done} 节，等待页面加载...")
                        time.sleep(7 + random.uniform(0.8,3.2))
                        curr_frame = grab_region(video_area, True)
                        if compute_mse(prev_frame, curr_frame) < video_mse_threshold:
                            print("  视频未自动播放 -> 再次点击播放区")
                            safe_click(px, py)
                        else:
                            print("  新视频自动播放中")
                        break
                    else:
                        print("  检测到弹题 -> 尝试点击答题区并关闭弹窗")
                        for _ in range(10):
                            rx = quiz_area[0] + np.random.randint(max(1, quiz_area[2]-2))
                            ry = quiz_area[1] + np.random.randint(max(1, quiz_area[3]-2))
                            safe_click(rx, ry)
                            time.sleep(0.15 + random.uniform(0,0.05))
                        cx = close_area[0] + close_area[2] // 2
                        cy = close_area[1] + close_area[3] // 2
                        safe_click(cx, cy)
                        print("  已关闭弹窗，等待 7 秒后尝试重新播放")
                        time.sleep(7 + random.uniform(0.6,2.0))
                        safe_click(px, py)
                        static_count = 0
                        prev_frame = grab_region(video_area, True)

        except KeyboardInterrupt:
            print("\n用户中断，退出程序")
            break
        except Exception:
            print("执行出错，打印异常")
            traceback.print_exc()
            time.sleep(3)

# -------------------- 主入口 --------------------
def main():
    print("智慧树自动化脚本")
    print("请确保智慧树页面已打开且布局稳定")
    print("-"*70)
    rois = {}
    coords = select_roi("1/4 【视频区】")
    if coords:
        rois['video_area'] = {'x': coords[0], 'y': coords[1], 'w': coords[2], 'h': coords[3]}
    coords = select_roi("2/4 【下一课区域】")
    if coords:
        rois['next_course_area'] = {'x': coords[0], 'y': coords[1], 'w': coords[2], 'h': coords[3]}
    coords = select_roi("3/4 【答题区】")
    if coords:
        rois['quiz_area'] = {'x': coords[0], 'y': coords[1], 'w': coords[2], 'h': coords[3]}
    coords = select_roi("4/4 【关闭区】")
    if coords:
        rois['close_area'] = {'x': coords[0], 'y': coords[1], 'w': coords[2], 'h': coords[3]}

    x, y, w, h = rois['close_area']['x'], rois['close_area']['y'], rois['close_area']['w'], rois['close_area']['h']
    initial_close = grab_region((x, y, w, h), True)
    viewer = show_image_non_blocking(initial_close, "关闭区截图 (关闭窗口继续)")
    while viewer.isVisible():
        app.processEvents()
        time.sleep(0.05)

    with open('rois.json', 'w', encoding='utf-8') as f:
        json.dump(rois, f, indent=4, ensure_ascii=False)
    print("ROI 已保存到 rois.json")

    print("\n默认参数：帧检查间隔=2s, 视频静止MSE阈值=1.0, 连续静止次数=3, 关闭区变化阈值=100")
    inp = input("是否使用默认参数？(y/n): ").strip().lower()
    if inp == 'y':
        run_automation(rois, initial_close)
    else:
        try:
            ci = float(input("帧检测间隔(秒,默认2.0): ") or 2.0)
            vm = float(input("视频区两帧MSE阈值(默认1.0): ") or 1.0)
            sr = int(input("连续静止次数(默认3): ") or 3)
            cm = float(input("关闭区MSE阈值(默认100): ") or 100.0)
        except Exception:
            print("输入不合法，使用默认参数")
            ci, vm, sr, cm = 2.0, 1.0, 3, 100.0
        run_automation(rois, initial_close, check_interval=ci,
                       video_mse_threshold=vm, static_required=sr,
                       close_mse_threshold=cm)

if __name__ == "__main__":
    main()

'''
                       _oo0oo_
                      o8888888o
                      88" . "88
                      (| -_- |)
                      0\  =  /0
                    ___/`---'\___
                  .' \\|     |// '.
                 / \\|||  :  |||// \
                / _||||| -:- |||||- \
               |   | \\\  -  /// |   |
               | \_|  ''\---/''  |_/ |
               \  .-\__  '-'  ___/-. /
             ___'. .'  /--.--\  `. .'___
          ."" '<  `.___\_<|>_/___.' >' "".
         | | :  `- \`.;`\ _ /`;.`/ - ` : | |
         \  \ `_.   \_ __\ /__ _/   .-` /  /
     =====`-.____`.___ \_____/___.-`___.-'=====
                       `=---='


     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

               佛祖保佑         永无BUG
'''