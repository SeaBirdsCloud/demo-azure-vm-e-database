from flask import Flask, render_template, request
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    message = None
    if request.method == 'POST':
        host = request.form['host']
        user = request.form['user']
        password = request.form['password']
        database = request.form['database']

        try:
            conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database
            )
            if conn.is_connected():
                db_info = conn.get_server_info()
                message = f"✅ Conectado com sucesso ao MySQL versão {db_info}"
        except Error as e:
            message = f"❌ Erro ao conectar: {e}"
        finally:
            if 'conn' in locals() and conn.is_connected():
                conn.close()

    return render_template('index.html', message=message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
