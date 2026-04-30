
# from src.common.setup_log import SetupLogger


class CommonUtilCodes:
    def __init__(self):
        # self.logger = SetupLogger.get_logger()
        a="b"

    def check_and_make_list(self, input_data):
        """
        인풋을 확인하고 리스트면 그대로 리턴, 아닌 경우 리스트로 감싸서 리턴
        :param input_data: 리스트 형태로 리턴 받아야 하는 값
        :return: 리스트면 그대로 리턴, None 이면 빈 리스트, 둘 다 아닌 경우 리스트로 감싸 리턴
        """
        if isinstance(input_data, list):
            return input_data
        elif input_data is None:
            return []  # None을 빈 리스트로 변환
        else:
            return [input_data]