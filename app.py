from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = "chave-super-secreta"
connection_params = {}
selected_db = None

def get_connection(db=None):
    global connection_params
    params = connection_params.copy()
    if db:
        params["database"] = db
    return mysql.connector.connect(**params)


@app.route('/', methods=['GET', 'POST'])
def index():
    global connection_params
    if request.method == 'POST':
        connection_params = {
            'host': request.form['host'],
            'user': request.form['user'],
            'password': request.form['password']
        }
        try:
            conn = get_connection()
            if conn.is_connected():
                flash("✅ Conexão bem-sucedida!", "success")
                return redirect(url_for('dashboard'))
        except Error as e:
            flash(f"❌ Erro: {e}", "danger")
    return render_template('index.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    global selected_db
    if not connection_params:
        return redirect(url_for('index'))
    message = None
    db_name = request.args.get('db')

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Criar novo banco
        if request.method == 'POST' and 'new_db' in request.form:
            new_db = request.form['new_db']
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{new_db}`")
            message = f"✅ Banco '{new_db}' criado."

        # Excluir banco
        elif request.method == 'POST' and 'delete_db' in request.form:
            delete_db = request.form['delete_db']
            if delete_db not in ['mysql', 'sys', 'performance_schema', 'information_schema']:
                cursor.execute(f"DROP DATABASE IF EXISTS `{delete_db}`")
                message = f"🗑️ Banco '{delete_db}' excluído com sucesso."
            else:
                message = f"⚠️ O banco '{delete_db}' é protegido e não pode ser excluído."

        # Excluir tabela
        elif request.method == 'POST' and 'delete_table' in request.form and db_name:
            delete_table = request.form['delete_table']
            conn2 = get_connection(db_name)
            cursor2 = conn2.cursor()
            cursor2.execute(f"DROP TABLE IF EXISTS `{delete_table}`")
            conn2.commit()
            message = f"🗑️ Tabela '{delete_table}' excluída com sucesso."
            conn2.close()

        # Listar bancos e tabelas
        cursor.execute("SHOW DATABASES")
        databases = [row[0] for row in cursor.fetchall()]
        selected_db = db_name
        tables = []
        if db_name:
            conn2 = get_connection(db_name)
            cursor2 = conn2.cursor()
            cursor2.execute("SHOW TABLES")
            tables = [row[0] for row in cursor2.fetchall()]
            conn2.close()

    except Error as e:
        message = f"❌ Erro: {e}"
        databases, tables = [], []
    finally:
        if conn.is_connected():
            conn.close()

    return render_template('dashboard.html', databases=databases, tables=tables, selected_db=db_name, message=message)

@app.route('/create_table/<db>', methods=['GET', 'POST'])
def create_table(db):
    message = None
    try:
        conn = get_connection(db)
        cursor = conn.cursor()

        # Buscar tabelas existentes (para popular selects de FK)
        cursor.execute("SHOW TABLES")
        existing_tables = [row[0] for row in cursor.fetchall()]

        # Estruturas das tabelas existentes
        tables_columns = {}
        for t in existing_tables:
            cursor.execute(f"SHOW COLUMNS FROM `{t}`")
            tables_columns[t] = [col[0] for col in cursor.fetchall()]

        if request.method == 'POST':
            table_name = request.form['table_name']
            total = int(request.form['total_columns'])
            columns = []
            foreign_keys = []

            # Coleta de colunas
            for i in range(total):
                name = request.form[f'name_{i}']
                col_type = request.form[f'type_{i}']
                length = request.form.get(f'length_{i}', '')
                pk = 'PRIMARY KEY' if request.form.get(f'pk_{i}') else ''
                ai = 'AUTO_INCREMENT' if request.form.get(f'ai_{i}') else ''
                nullable = '' if request.form.get(f'notnull_{i}') else 'NULL'
                full_type = f"{col_type}({length})" if length else col_type
                columns.append(f"`{name}` {full_type} {nullable} {pk} {ai}")

            # Coleta das FKs
            fk_count = int(request.form.get('fk_count', 0))
            for i in range(fk_count):
                fk_col = request.form.get(f'fk_col_{i}')
                ref_table = request.form.get(f'fk_ref_table_{i}')
                ref_col = request.form.get(f'fk_ref_col_{i}')
                if fk_col and ref_table and ref_col:
                    foreign_keys.append(
                        f"FOREIGN KEY (`{fk_col}`) REFERENCES `{ref_table}`(`{ref_col}`)"
                    )

            all_defs = columns + foreign_keys
            query = f"CREATE TABLE `{table_name}` ({', '.join(all_defs)}) ENGINE=InnoDB"

            cursor.execute(query)
            conn.commit()
            flash(f"✅ Tabela '{table_name}' criada com sucesso!", "success")
            return redirect(url_for('dashboard', db=db))

    except Error as e:
        message = f"❌ Erro ao criar tabela: {e}"
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

    return render_template('create_table.html', db=db, message=message,
                           existing_tables=existing_tables, tables_columns=tables_columns)

@app.route('/table/<db>/<table>', methods=['GET', 'POST'])
def table(db, table):
    rows, columns, message, structure = [], [], None, []
    try:
        conn = get_connection(db)
        cursor = conn.cursor()

        # Excluir registro
        if request.method == 'POST' and 'delete' in request.form:
            pk = request.form['delete']
            cursor.execute(f"DELETE FROM `{table}` WHERE id = %s", (pk,))
            conn.commit()
            flash("Registro excluído com sucesso!", "success")

        # Adicionar registro
        elif request.method == 'POST' and 'add' in request.form:
            cols = request.form.getlist('col')
            vals = request.form.getlist('val')
            query = f"INSERT INTO `{table}` ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(vals))})"
            cursor.execute(query, vals)
            conn.commit()
            flash("Registro adicionado!", "success")

        # Obter estrutura da tabela
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")
        structure = cursor.fetchall()
        columns = [col[0] for col in structure]

        # Obter dados
        cursor.execute(f"SELECT * FROM `{table}`")
        rows = cursor.fetchall()

    except Error as e:
        message = f"❌ Erro: {e}"

    finally:
        if conn.is_connected():
            conn.close()

    return render_template(
        'table.html',
        db=db,
        table=table,
        columns=columns,
        rows=rows,
        structure=structure,
        message=message
    )

@app.route('/query/<db>', methods=['GET', 'POST'])
def query(db):
    result, message = None, None
    try:
        conn = get_connection(db)
        cursor = conn.cursor()
        if request.method == 'POST':
            sql = request.form['sql']
            cursor.execute(sql)
            if sql.strip().lower().startswith("select"):
                result = cursor.fetchall()
                columns = cursor.column_names
                return render_template('query.html', db=db, result=result, columns=columns)
            else:
                conn.commit()
                flash("✅ Comando executado!", "success")
    except Error as e:
        message = f"❌ Erro: {e}"
    finally:
        if conn.is_connected():
            conn.close()
    return render_template('query.html', db=db, message=message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
