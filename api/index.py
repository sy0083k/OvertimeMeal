from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime, time
import os
import pandas as pd
from io import BytesIO
from werkzeug.utils import secure_filename

app = Flask(__name__)

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
        min_hours = int(request.form.get('minHours', 60))
        s1 = request.form.get('startTime1')
        e1 = request.form.get('endTime1')
        s2 = request.form.get('startTime2')
        e2 = request.form.get('endTime2')
        s3 = request.form.get('startTime3')         
        
        file = request.files['file']
        if file and allowed_file(file.filename):
            # 엑셀 로드 및 컬럼 정리
            df = pd.read_excel(file, index_col=0, usecols=[1,2,3,4,5,6,10,11,12,17,18,21,28])
            df = df.query("자료구분 == '정산' and 결재상태 == '처리'")
            df.columns = df.columns.str.strip().str.replace(' ', '_', regex=False).str.replace('(', '_').str.replace(')', '')
                     
            # 기본 날짜 처리
            df['근무일자'] = pd.to_datetime(df['근무일자'])
            df['근무일자2'] = df['근무일자'].dt.day
            df['근무일자'] = df['근무일자'].dt.date

            # 3. 텍스트 상태로 급식비 판정 로직 적용
            df['meal'] = 0
            # 평일 기준
            df.loc[(df.휴일구분 == '평일') & (df.수당시간_분 >= 60), 'meal'] = 1
            
            # 휴일 기준 (텍스트 비교)
            is_holiday = (df.휴일구분 == '휴일')
            df.loc[is_holiday & (df.수당시간_분 > min_hours), 'meal'] = 1
            
            # 미지급 조건 (텍스트 간 크기 비교)
            if s1 and e1:
                df.loc[is_holiday & (df.출근_실제 >= s1) & (df.퇴근_실제 <= e1), 'meal'] = 0
            if s2 and e2:
                df.loc[is_holiday & (df.출근_실제 >= s2) & (df.퇴근_실제 <= e2), 'meal'] = 0
            if s3:
                df.loc[is_holiday & (df.출근_실제 >= s3), 'meal'] = 0

            df['pay'] = df['meal'] * 8000
            
            # 개인별 집계 데이터 생성
            summary_df = df.groupby('성명')[['meal', 'pay']].sum().reset_index()

            # 4. 결과 저장 (openpyxl 사용)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='report')
                # 시트 2: 개인별 총계
                summary_df.to_excel(writer, sheet_name='summary', index=False)                
                # 시트 3: 날짜별 피벗 (누가 몇 일에 먹었나)
                pivot_df = df[df['meal'] == 1].pivot(index='성명', columns='근무일자2', values='근무일자2')
                pivot_df.to_excel(writer, sheet_name='pivot_report')
            
            output.seek(0)
            return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             as_attachment=True, download_name='급식비_계산결과.xlsx')
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True) 