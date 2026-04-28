import os
import subprocess
from pathlib import Path
from datetime import datetime


class PathConst:
    def __init__(self):
        # 경로 관련
        self.DATA_PATH = "data"
        self.RESULT_PATH = "result"
        self.LOG_PATH = "logs"
        self.TEMP_PATH = "temp"
        self.NOTEBOOKS_PATH = "notebooks"


class FilePathClass(PathConst):
    def __init__(self):
        super().__init__()
        # root 경로
        self.root_path = self.get_project_root_path()
        # 사용자 정의 폴더
        self.data_path = self.DATA_PATH
        self.result_path = self.RESULT_PATH
        self.log_path = self.LOG_PATH
        self.temp_path = self.TEMP_PATH
        self.notebooks_path = self.NOTEBOOKS_PATH
        # 바탕화면 경로
        self.desktop_path = self.get_desktop_path()

        try:
            if not os.path.exists(self.root_path):
                raise ValueError
        except ValueError:
            print("폴더 확인")

    # 프로젝트 최상위 경로 추출 메서드
    def get_project_root_path(self):
        """
        현재 파일의 위치를 기준으로 프로젝트 최상위 경로를 반환
        :return: 프로젝트 최상위 경로
        """
        current_file = Path(__file__).resolve()
        project_root = current_file.parents[2]  # 파일로부터 두 단계 위의 디렉토리
        return str(project_root)

    def get_desktop_path(self):
        """
        os 환경에 따라 유저프로필을 찾고 바탕화면 경로 추출
        :return: 바탕화면 경로
        """
        if os.name == 'nt':  # Windows // 유저 프로필을 찾아 바탕화면 경로 추출
            return str(Path(os.environ['USERPROFILE']) / 'Desktop')
        elif os.name == 'posix':  # macOS or Linux
            return str(Path.home() / 'Desktop')
        else:
            return OSError(f"Failed to retrieve OS information.")

    def is_path_exist_check(self, path):
        """
        파일 또는 폴더 존재 여부 확인 함수
        :param path: 파일 혹은 폴더 경로
        :return:
        """
        if not os.path.exists(path):
            return False
        else:
            return True

    def make_path(self, path):
        """
        폴더 생성 함수
        :param path: 생성할 폴더 경로
        :return:
        """
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def get_log_path(self):
        """
        로그파일 경로 반환
        (log 폴더 경로 FIN_RAG/logs/)
        :return:
        """
        folder = self.root_path + os.sep + self.log_path + os.sep
        return self.make_path(folder)

    def get_month_log_path(self):
        """
        월별 로그 파일 경로 반환
        (FIN_RAG/logs/{YYYYmm}/)
        :return:
        """
        folder = self.root_path + os.sep + self.log_path + os.sep + datetime.now().strftime('%Y_%m') + os.sep
        return self.make_path(folder)

    def get_data_path(self):
        """
        data 폴더 경로 반환
        (FIN_RAG/data/)
        :return:
        """
        folder = self.root_path + os.sep + self.data_path + os.sep
        return self.make_path(folder)

    def get_result_path(self):
        """
        결과 파일 경로 반환(FIN_RAG/data/result/)
        :return:
        """
        folder = self.root_path + os.sep + self.data_path + os.sep + self.result_path + os.sep
        return self.make_path(folder)

    def get_temp_path(self):
        """
        임시(temp) 폴더 경로 반환(FIN_RAG/data/temp/)
        :return:
        """
        folder = self.root_path + os.sep + self.data_path + os.sep + self.temp_path + os.sep
        return self.make_path(folder)
