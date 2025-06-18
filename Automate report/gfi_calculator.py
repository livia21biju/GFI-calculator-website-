from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('gfi_calculator.html')

@app.route('/add', methods=['POST'])
def add_numbers():
    try:
        numbers = request.form.getlist('number')  # get all inputs named 'number'
        numbers = [float(n) for n in numbers if n.strip() != '']
        result = sum(numbers)
    except Exception as e:
        result = f"Error: {e}"

    return render_template('gfi_calculator.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)
