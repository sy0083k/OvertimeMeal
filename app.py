from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime, time
import os
import pandas as pd
from io import BytesIO

app = Flask(__name__)

# [개선] 사용할 원본 컬럼명과 내부용 표준 이름을 매핑합니다.
COLUMN_MAP = {
    '출근(실제)': '출근_실제',
    '퇴근(실제)': '퇴근_실제',
    '수당시간(분)': '수당시간_분',
}
# 역매핑 (저장 시 다시 괄호 포함 이름으로 돌리기 위함)
REVERSE_COLUMN_MAP = {v: k for k, v in COLUMN_MAP.items()}

# Add template folder configuration
template_dir = os.path.abspath(os.path.dirname(__file__))
app.template_folder = os.path.join(template_dir, 'templates')

# Add file upload configuration
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        # 1. FormData에서 직접 텍스트 값 추출
        unit_price = int(request.form.get('unitPrice', 9000)) # [적용] 사용자 입력 단가
        min_hours = int(request.form.get('minHours', 60))
        s1 = request.form.get('startTime1')
        e1 = request.form.get('endTime1')
        s2 = request.form.get('startTime2')
        e2 = request.form.get('endTime2')
        s3 = request.form.get('startTime3')         
        
        file = request.files['file']
        if file and allowed_file(file.filename):
            # 1. 사용할 실제 컬럼명 리스트 (괄호 포함 원본 그대로)
            target_columns = ['No.', '근무일자', '부서', '직급', '고유식별번호', '성명', '휴일구분', '자료구분', '결재상태', '출근(실제)', '퇴근(실제)', '수당시간(분)']
            # 엑셀 로드 및 컬럼 정리
            df = pd.read_excel(file, index_col=0, usecols=target_columns)
            df = df.query("자료구분 == '정산' and 결재상태 == '처리'")
            df.columns = df.columns.str.strip().str.replace(' ', '_', regex=False).str.replace('(', '_').str.replace(')', '')
                     
            # 기본 날짜 처리
            df['근무일자'] = pd.to_datetime(df['근무일자'])
            df['근무일자2'] = df['근무일자'].dt.day
            df['근무일자'] = df['근무일자'].dt.date

            # 3. 텍스트 상태로 급식비 판정 로직 적용
            df['식수'] = 0
            # 평일 기준
            df.loc[(df.휴일구분 == '평일') & (df.수당시간_분 >= 60), '식수'] = 1
            
            # 휴일 기준 (텍스트 비교)
            is_holiday = (df.휴일구분 == '휴일')
            df.loc[is_holiday & (df.수당시간_분 >= min_hours), '식수'] = 1
            
            # 미지급 조건 (텍스트 간 크기 비교)
            if s1 and e1:
                df.loc[is_holiday & (df.출근_실제 >= s1) & (df.퇴근_실제 <= e1), '식수'] = 0
            if s2 and e2:
                df.loc[is_holiday & (df.출근_실제 >= s2) & (df.퇴근_실제 <= e2), '식수'] = 0
            if s3:
                df.loc[is_holiday & (df.출근_실제 >= s3), '식수'] = 0

            df['식대'] = df['식수'] * unit_price
            
            # 개인별 집계 데이터 생성
            summary_df = df.groupby('성명')[['식수', '식대']].sum().reset_index()

            # 5. 저장 직전 컬럼명 복구 (예쁜 이름으로 변경)
            # 분석용으로 추가한 내부 컬럼(day 등) 제외하고 필요한 것만 매핑하여 복구
            export_df = df.rename(columns=REVERSE_COLUMN_MAP)
        
            # 4. 결과 저장 (openpyxl 사용)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                export_df.to_excel(writer, sheet_name='report')
                # 시트 2: 개인별 총계
                summary_df.to_excel(writer, sheet_name='summary', index=False)                
                # 시트 3: 날짜별 피벗 (누가 몇 일에 먹었나)
                pivot_df = df[df['식수'] == 1].pivot(index='성명', columns='근무일자2', values='근무일자2')
                pivot_df.to_excel(writer, sheet_name='pivot_report')
            
            output.seek(0)
            return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             as_attachment=True, download_name='계산결과.xlsx')
    except Exception as e:
        print(f"Error: {e}") # 서버 로그 확인용
        return jsonify({'error': '서버 내부 오류가 발생했습니다.'}), 500

if __name__ == '__main__':
    # 로컬 테스트용. Render 배포 시에는 gunicorn이 실행하므로 이 부분은 무시됨.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 