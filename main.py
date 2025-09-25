import sys
import json
import requests
import threading
from urllib.parse import urlparse, parse_qs
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QFormLayout
from PyQt5.QtCore import QObject, pyqtSignal, QThread

class Worker(QObject):
    """
    后台工作线程，用于处理网络请求
    """
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, homework_id, token):
        super().__init__()
        self.homework_id = homework_id
        self.token = token

    def run(self):
        """答题逻辑"""
        try:
            headers = {
                'X-Access-Token': self.token,
                'Host': 'lcu.eduplus.net',
                'Content-Type': 'application/json'
            }
            
            homework_id = self.homework_id

            self.log_signal.emit("步骤一: 正在获取题目列表...")
            questions_url = f"https://lcu.eduplus.net/api/course/homeworkQuestions/student?homeworkId={homework_id}"
            response = requests.get(questions_url, headers=headers)
            response.raise_for_status()
            
            questions_data = response.json()
            question_ids = [item['id'] for item in questions_data.get('data', [])]
            
            if not question_ids:
                self.log_signal.emit("错误: 未找到任何题目ID。")
                self.finished_signal.emit()
                return
            
            self.log_signal.emit(f"成功获取到 {len(question_ids)} 道题目。")

            for i, question_id in enumerate(question_ids):
                try:
                    self.log_signal.emit(f"正在处理第 {i+1}/{len(question_ids)} 题: {question_id}")
                    question_detail_url = f"https://lcu.eduplus.net/api/course/homeworkQuestions/{question_id}"
                    detail_response = requests.get(question_detail_url, headers=headers)
                    detail_response.raise_for_status()
                    answer = detail_response.json().get('data', {}).get('answer')

                    if not answer:
                        self.log_signal.emit(f"警告: 题目 {question_id} 未找到答案，跳过。")
                        continue
                    
                    self.log_signal.emit(f"获取到答案: {answer}")

                    submit_url = "https://lcu.eduplus.net/api/course/hwAnswers/answer"
                    payload = {
                        "homeworkQuestionId": question_id,
                        "userAnswer": answer
                    }
                    submit_response = requests.put(submit_url, headers=headers, data=json.dumps(payload))
                    submit_response.raise_for_status()
                    
                    self.log_signal.emit(f"第 {i+1} 题提交成功。")

                except requests.exceptions.RequestException as e:
                    self.log_signal.emit(f"处理题目 {question_id} 时发生网络错误: {e}")
                except json.JSONDecodeError:
                    self.log_signal.emit(f"处理题目 {question_id} 时解析响应失败。")
                except Exception as e:
                    self.log_signal.emit(f"处理题目 {question_id} 时发生未知错误: {e}")

            self.log_signal.emit("所有题目处理完毕！")

        except requests.exceptions.RequestException as e:
            self.log_signal.emit(f"发生网络错误: {e}")
        except json.JSONDecodeError:
            self.log_signal.emit("解析初始题目列表失败，请检查返回数据是否为有效的JSON格式。")
        except Exception as e:
            self.log_signal.emit(f"发生未知错误: {e}")
        finally:
            self.finished_signal.emit()

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('自动答题程序')
        self.setGeometry(300, 300, 600, 400)

        # Layouts
        main_layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Widgets
        self.homework_id_entry = QLineEdit()
        self.token_entry = QLineEdit()
        self.start_button = QPushButton('开始答题')
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)

        # Form Layout
        form_layout.addRow(QLabel('homeworkId:'), self.homework_id_entry)
        form_layout.addRow(QLabel('X-Access-Token:'), self.token_entry)

        # Button Layout
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.start_button)

        # Main Layout
        main_layout.addLayout(form_layout)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.log_area)

        self.setLayout(main_layout)

        # Connections
        self.start_button.clicked.connect(self.start_task)

    def log(self, message):
        self.log_area.append(message)

    def on_task_finished(self):
        self.start_button.setEnabled(True)
        self.thread.quit()
        self.thread.wait()

    def start_task(self):
        homework_id = self.homework_id_entry.text()
        token = self.token_entry.text()

        if not homework_id or not token:
            self.log("错误: homeworkId 和 X-Access-Token 不能为空。")
            return

        self.start_button.setEnabled(False)
        self.log("任务开始...")

        # 使用 QThread 处理后台任务
        self.thread = QThread()
        self.worker = Worker(homework_id, token)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_task_finished)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    ex.show()
    sys.exit(app.exec_())
