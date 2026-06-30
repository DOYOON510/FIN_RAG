import os
import csv
import datetime

class ValidateFiles:
    def __init__(self):
        self.base_dir = r"C:\Users\user\Desktop\test\test_data"
        self.dir_nm_38 = "검증실행결과파일_38"
        self.dir_nm_41 = "검증실행결과파일_41"
        self.oud_dir = r"C:\Users\user\Desktop\test\validate"
        self.current_date = datetime.datetime.now().strftime("%Y%m%d")

    def read_header_and_lines(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                lines = [line.rstrip() for line in f if line.rstrip()]

                if not lines:
                    header = None
                    data_lines = None
                    row_cnt = None

                else:
                    header = lines[0].split(",")
                    data_lines = lines[1:]
                    row_cnt = len(data_lines)

                result = {"header": header, "data_lines": data_lines, "row_cnt": row_cnt}
            return result

        except FileNotFoundError:
            print(f"{file_path} - 경로에 해당 파일이 존재하지 않습니다.")
            return False

    def find_and_save_mismatch_row(self, file, dir_path, file_info_41, file_info_38):
        """

        """
        mismatch_row_data_list = []
        data_lines_41 = file_info_41["data_lines"]
        data_lines_38 = file_info_38["data_lines"]

        header_list = file_info_38["header"]
        dtm_col_id_list = [idx for idx, header in enumerate(file_info_38["header"]) if "_dtm" or "일시" in header]

        for row_idx, (row_41, row_38) in enumerate(zip(data_lines_41, data_lines_38), start=1):
            row_List_41 = row_41.split(",")
            row_list_38 = row_38.split(",")

            if row_list_41 != row_list_38:
                for idx, (data_41, data_38) in enumerate(zip(row_List_41, row_list_38)):
                    if data_41 != data_38:
                        if row_idx in [saved_data[o] for saved_data in mismatch_row_data_list]:
                            continue
                        if idx in dtm_col_idx_list:
                            continue
                        else:
                            file_row_38 = [row_idx, "3,8", dir_path.replace(self.dir_nm_41, self.dir_nm38)]
                            file_row_38.extend(row_38.split(","))
                            file_row_41 = [row_idx, "4.1", dir_path]
                            file_row_41.extend(row_41.split(", "))

                        mismatch_row_data_list.append(file_row_38)
                        mismatch_row_data_list.append(file_row_41)

        if len(mismatch_row_data_list) == 0:
            return None
        else:
            save_dir = os.path.join(self.out_dir, f"data_mismatched_{self.current_date}")
            os.makedirs(save_dir, exist_ok=True)
            with open(os.path.join(save_dir, f"{os.path.splitext(file)[0]}_mismatch_row.csv"), "w", newline="",encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerows(["row_num", "version", "dir_path"] + header_list)
                writer.writerows(mismatch_row_data_list)
            print(f"{os.path.splitext(file)[0]}_mismatch_row.csv - 오류 내역 파일 저장 완료")
            return True

    def validate_files(self):
        """
        Brightics 3.8과 4.1의 모델 결과 파일을 비교 검증하고, 오류 파일을 생성하는 할수
        :return : 데이터 row 값이 불일치 하는 두 파일의 경토
        """
        dir_path_41 = os.path.join(self.base_dir, self.dir_nm_41)
        validate_result_rows = []  # 검증 결과를 저장하기 위한 row 리스트 생성

        error_cnt = 0
        for root, dirs, files in os. walk(dir_path_41):
            if files:
                for file in files:
                    file_path_41 = os.path.join(root, file)
                    file_path_38 = file_path_41.replace(self.dir_nm_41, self.dir_nm_38)

                    file_info_41 = self.read_header_and_lines(file_path_41)
                    file_info_38 = self.read_header_and_lines(file_path_38)
                    dir_path = "\\".join(root.split("\\")[6:])

                    # 파일 경로 오류인 경우
                    if file_info_41 == False:
                        error_msg = "FILE_NOT_FOUND"
                        error_file = "v4.1"

                    elif file_info_38 == False:
                        error_msg = "FILE_NOT_FOUND"
                        error_file = "v3.8"

                    # 빈 파일인 경우
                    elif file_info_41["header"] is None:
                        error_msg = "NO_DATA_IN_FILE"
                        error_file = "v4.1"

                    elif file_info_38["header"] is None:
                        error_msg = "NO_DATA_IN_FILE"
                        error_file = "v3.8"

                    # 헤더가 일치하지 않는 경우
                    elif file_info_41["header"] != file_info_38["header"]:
                        error_msg = "COULMN_MISMATCH"

                    # row 수가 일치하지 않는 경우
                    elif file_info_41["row_cnt"] != file_info_38["row_cnt"]:
                        error_msg = "ROW_CNT_MISMATCH"

                    # row의 데이터 값이 일치하지 않는 경우
                    elif file_info_41["data_lines"] != file_info_38["data_lines"]:
                        # 이후 2차 검증(row 번호 찾기)을 위해, 두 파일 경로 모두 저장하여 반환
                        save_result = self.find_and_save_mismatch_row(file, dir_path, file_info_41, file_info_38)
                        if save_result is None:
                            error_msg = None
                        else:
                            error_msg = "DATA_MISMATCH"

                    else:
                        error_msg = None

                    dir_path = "\\".join(dir_path.split("\\")[1:])

                    if error_msg:
                        error_cnt += 1
                        print(f"{file_path_41} - 오류 발생: {error_msg}")
                        match_yn = "N"
                        # 파일 자체 문제인 경우, 문제가 되는 파일의 버전을 남기기 위해 분기 처리
                        if error_msg in ["FILE_NOT_FOUND", "NO_DATA_IN_FILE"]:
                            error_msg = f"{error_msg}_IN_{error_file}"
                            result_row = [file, dir_path, match_yn, None, None, None, None, error_msg]

                        else:
                            result_row = [file, dir_path, match_yn, file_info_38["row_cnt"], file_info_41["row_cnt"],
                                          len(file_info_38["header"]), len(file_info_41["header"]), error_msg]
                    else:
                        match_yn = "Y"
                        result_row = [file, dir_path, match_yn, file_info_38["row_cnt"], file_info_41["row_cnt"],
                                      len(file_info_38["header"]), len(file_info_41["header"]), error_msg]
                    validate_result_rows.append(result_row)
        print(f"총 ERROR 발생 건수: {error_cnt}")

        with open(os.path.join(self.out_dir, f"validate_result_{self.current_date}.csv"), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerows(["valid_file_id", "dir_path", "matched_yn", "row_cnt_v3.8", "row_cnt_v4.1", "header_cnt_v3.8", "header_cnt_v4.1", "error_msg"])
            writer.writerows(validate_result_rows)

        return True