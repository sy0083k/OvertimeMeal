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

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        min_hours = int(data.get('minHours', 0))
        
        # Process time inputs
        times = {
            'start1': datetime.strptime(data['startTime1'], '%H:%M').time(),
            'end1': datetime.strptime(data['endTime1'], '%H:%M').time(),
            'start2': datetime.strptime(data['startTime2'], '%H:%M').time(),
            'end2': datetime.strptime(data['endTime2'], '%H:%M').time(),
            'start3': datetime.strptime(data['startTime3'], '%H:%M').time()
        }

        # Calculate meal allowance based on rules
        result = {
            'meal_allowance': False,
            'reason': ''
        }

        # Rule 1: Minimum hours check
        if min_hours < 60:
            result['reason'] = '최소수당시간이 1시간 미만입니다.'
            return jsonify(result)

        # Rule 2: 09:00-12:00 check
        if (times['start1'] > time(9, 0) and times['end1'] < time(12, 0)) or \
           (times['start2'] > time(9, 0) and times['end2'] < time(12, 0)):
            result['reason'] = '09시 후 출근해 12시 전 퇴근'
            return jsonify(result)

        # Rule 3: 13:00-18:00 check
        if (times['start1'] > time(13, 0) and times['end1'] < time(18, 0)) or \
           (times['start2'] > time(13, 0) and times['end2'] < time(18, 0)):
            result['reason'] = '13시 후 출근해 18시 전 퇴근'
            return jsonify(result)

        # Rule 4: After 19:00 check
        if times['start1'] > time(19, 0) or \
           times['start2'] > time(19, 0) or \
           times['start3'] > time(19, 0):
            result['reason'] = '19시 후 출근'
            return jsonify(result)

        # If all rules pass, grant meal allowance
        result['meal_allowance'] = True
        result['amount'] = 8000  # 8000 won per meal

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': '파일이 전송되지 않았습니다.'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '파일이 선택되지 않았습니다.'}), 400
        
        if file and allowed_file(file.filename):
            # Read Excel file directly from the uploaded file
            df = pd.read_excel(file, index_col=0, usecols=[1,2,3,4,5,6,10,11,12,17,18,21,28])
            df = df.query("자료구분 == '정산' and 결재상태 == '처리'")
            
            # Create Excel file in memory
            output = BytesIO()
            df.to_excel(output)
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='result.xlsx'
            )
        
        return jsonify({'error': '허용되지 않는 파일 형식입니다.'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True) 