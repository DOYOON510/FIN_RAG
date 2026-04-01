# from src.common.setup_log import SetupLogger

"""
커밋 시 폴더 생성을 위한 덤프 파일입니다. 삭제해도 무방합니다.
This is a dump file for creating folders during commit. You can delete it.
"""
class Analysis:
    def __init__(self):
        self.sl = SetupLogger()
        self.logger = self.sl.get_logger()

    def perform_analysis(self):
        # 분석 로직
        pass

    def build_model(self):
        # 모델 구축 로직
        pass

    def train_model(self):
        # 모델 훈련 로직
        pass

    def evaluate_model(self):
        # 모델 평가 로직
        pass
