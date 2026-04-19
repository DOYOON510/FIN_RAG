import os
import logging
import inspect
from datetime import datetime

from src.common.file_path import FilePathClass


class SetupLogger:
    """
    로그 생성 객체 선언
    logger = SetupLogger.get_logger() 형태로 사용
    """
    _logger = None
    _log_date = None  # 현재 설정된 로그 파일의 날짜

    @classmethod
    def setup_logger(cls):
        """
        logger를 설정하는 함수 (날짜가 변경되면 새 파일 생성)
        """
        # Get the name of the calling module
        caller_frame = inspect.stack()[1]  # 호출된 함수의 스택의 정보를 가져오기
        caller_module = inspect.getmodule(caller_frame[0])  # 호출한 프레임 객체의 모듈 객체를 가져오기
        caller_name = os.path.splitext(os.path.basename(caller_module.__file__))[0]  # 호출한 모듈의 파일 이름 가져오기

        # Create a custom logger
        # logging.setLoggerClass(CustomLogger)  # error_with_code() 사용하는 경우에만 활성화 필요

        logger = logging.getLogger(caller_name)

        # 기존 핸들러 제거 (날짜가 바뀌었을 경우)
        if logger.hasHandlers():
            logger.handlers.clear()

        # Set the level of logger(Debug로 고정)
        logger.setLevel(logging.DEBUG)

        # 로그 폴더 경로
        fp = FilePathClass()
        log_path = fp.get_month_log_path()

        # 새로운 날짜 설정
        cls._log_date = datetime.now().strftime('%Y%m%d')

        # 화면에 보여줄 콘솔 로그 핸들러 정의
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('[%(levelname)s] - [%(filename)s, %(lineno)d] - [%(funcName)s] %(message)s')
        console_handler.setFormatter(console_format)

        # # INFO 이상 남는 일반 로그
        # info_log_filename = f"{datetime.now().strftime('%Y%m%d')}_info.log"
        # info_file_handler = logging.FileHandler(os.path.join(log_path, info_log_filename), encoding='utf-8')
        # info_file_handler.setLevel(logging.INFO)
        # info_file_format = logging.Formatter('%(asctime)s - [%(levelname)s] - [%(name)s, %(lineno)d] - [%(funcName)s] %(message)s')
        # info_file_handler.setFormatter(info_file_format)

        # DEBUG 이상 남는 상세 로그
        debug_log_filename = f"{datetime.now().strftime('%Y%m%d')}_debug.log"
        debug_file_handler = logging.FileHandler(os.path.join(log_path, debug_log_filename), encoding='utf-8')
        debug_file_handler.setLevel(logging.DEBUG)
        debug_file_format = logging.Formatter('%(asctime)s - [%(levelname)s] - [%(filename)s, %(lineno)d] - [%(funcName)s] %(message)s')
        debug_file_handler.setFormatter(debug_file_format)

        # Add handlers to the logger
        logger.addHandler(console_handler)
        # logger.addHandler(info_file_handler)
        logger.addHandler(debug_file_handler)

        # 변경된 logger를 클래스 속성에 저장
        cls._logger = logger

    @classmethod
    def get_logger(cls):
        """
        싱글톤 방식으로 logger를 반환하며, 날짜 변경 시 새로운 로그 파일 생성
        :return: logger
        """
        current_date = datetime.now().strftime('%Y%m%d')

        # 날짜가 바뀌면 새로운 로거 설정
        if cls._logger is None or cls._log_date != current_date:
            cls.setup_logger()

        return cls._logger
