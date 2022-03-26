import re
from typing_extensions import Self
from flask import Flask, request, template_rendered
from flask import url_for, redirect, flash
from flask import render_template
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
from numpy import identity, product
import random, string
from sqlalchemy import null
import cx_Oracle

## Oracle 連線
# cx_Oracle.init_oracle_client(lib_dir="./instantclient_19_8") # init Oracle instant client 位置
# connection = cx_Oracle.connect('account', 'password', cx_Oracle.makedsn('ip', 1521, 'orcl')) # 連線資訊
# cursor = connection.cursor()

## Flask-Login : 確保未登入者不能使用系統
app = Flask(__name__)
app.secret_key = 'Your Key'  
login_manager = LoginManager(app)
login_manager.login_view = 'login' # 假如沒有登入的話，要登入會導入 login 這個頁面

class User(UserMixin):
    
    pass

@login_manager.user_loader
def user_loader(userid):  
    user = User()
    user.id = userid
    cursor.prepare('SELECT IDENTITY, NAME FROM MEMBER WHERE MID = :id ')
    cursor.execute(None, {'id':userid})
    data = cursor.fetchone()
    user.role = data[0]
    user.name = data[1]
    return user 

# 主畫面
@app.route('/')
def index():
    return render_template('index.html')

# 登入頁面
@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':

        account = request.form['account']
        password = request.form['password']

        # 查詢看看有沒有這個資料
        # sql = 'SELECT ACCOUNT, PASSWORD, MID, IDENTITY, NAME FROM MEMBER WHERE ACCOUNT = \'' + account + '\''
        # cursor.execute(sql)
        cursor.prepare('SELECT ACCOUNT, PASSWORD, MID, IDENTITY, NAME FROM MEMBER WHERE ACCOUNT = :id ')
        cursor.execute(None, {'id': account})

        data = cursor.fetchall() # 抓去這個帳號的資料

        # 但是可能他輸入的是沒有的，所以下面我們 try 看看抓不抓得到
        try:
            DB_password = data[0][1] # true password
            user_id = data[0][2] # user_id
            identity = data[0][3] # user or manager

        # 抓不到的話 flash message '沒有此帳號' 給頁面
        except:
            flash('*沒有此帳號')
            return redirect(url_for('login'))

        if( DB_password == password ):
            user = User()
            user.id = user_id
            login_user(user)

            if( identity == 'user'):
                return redirect(url_for('bookstore'))
            else:
                return redirect(url_for('manager'))
        
        # 假如密碼不符合 則會 flash message '密碼錯誤' 給頁面
        else:
            flash('*密碼錯誤，請再試一次')
            return redirect(url_for('login'))

    
    return render_template('login.html')

# 註冊頁面
@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        user_name = request.form['username']
        user_account = request.form['account']
        user_password = request.form['password']
        user_identity = request.form['identity']
        
        # 抓取所有的會員帳號，因為下面要比對是否已經有這個帳號
        check_account =""" SELECT ACCOUNT FROM MEMBER """
        cursor.execute(check_account)
        exist_account = cursor.fetchall()
        account_list = []
        for i in exist_account:
            account_list.append(i[0])

        if(user_account in account_list):
            # 如果已經有這個帳號，就會給一個 flash message : 上面會顯示已經有這個帳號了
            flash('Falid!')
            return redirect(url_for('register'))
        else:
            # 在 SQL 裡有設定 member id 是 auto increment 所以第一個值給：null
            # 可參考的設定連結：https://www.abu.tw/2008/06/oracle-autoincrement.html
            cursor.prepare('INSERT INTO MEMBER VALUES (null, :name, :account, :password, :identity)')
            cursor.execute(None, {'name': user_name, 'account':user_account, 'password':user_password, 'identity':user_identity })
            connection.commit()
            return redirect(url_for('login'))

    return render_template('register.html')

# 書店內部
@app.route('/bookstore', methods=['GET', 'POST'])
@login_required # 使用者登入後才可以看
def bookstore():

    # 以防管理者誤闖
    if request.method == 'GET':
        if( current_user.role == 'manager'):
            flash('No permission')
            return redirect(url_for('manager'))

    # 查看書本的詳細資料（假如有收到 pid 的 request）
    if 'pid' in request.args:
        pid = request.args['pid']

        # 查詢這本書的詳細資訊
        cursor.prepare('SELECT * FROM PRODUCT WHERE PID = :id ')
        cursor.execute(None, {'id': pid})

        data = cursor.fetchone() 
        pname = data[1]
        price = data[2]
        category = data[3]

        product = {
            '商品編號': pid,
            '商品名稱': pname,
            '單價': price,
            '類別': category
        }

        # 把抓到的資料用 json 格式傳給 projuct.html 
        return render_template('product.html', data = product)

    # 沒有收到 pid 的 request 的話，代表只是要看所有的書
    sql = 'SELECT * FROM PRODUCT'
    cursor.execute(sql)
    book_row = cursor.fetchall()
    book_data = []
    for i in book_row:
        book = {
            '商品編號': i[0],
            '商品名稱': i[1]
        }
        book_data.append(book)

    # 抓取所有書的資料 用一個 List 包 Json 格式，在 html 裡可以用 for loop 呼叫
    return render_template('bookstore.html', book_data=book_data, user=current_user.name)

# 會員購物車
@app.route('/cart', methods=['GET', 'POST'])
@login_required # 使用者登入後才可以看
def cart():

    # 以防管理者誤闖
    if request.method == 'GET':
        if( current_user.role == 'manager'):
            flash('No permission')
            return redirect(url_for('manager'))

    # 回傳有 pid 代表要 加商品
    if request.method == 'POST':
        
        if "pid" in request.form :
            product_data = add_product()

        elif "delete" in request.form :
            pid = request.values.get('delete')
            user_id = current_user.id #找到現在使用者是誰
            cursor.prepare('SELECT * FROM CART WHERE MID = :id ')
            cursor.execute(None, {'id': user_id})
            tno = cursor.fetchone()[2] # 交易編號

            cursor.prepare(' DELETE FROM RECORD WHERE TNO=:tno and PID=:pid ')
            cursor.execute(None, {'tno': tno, 'pid':pid})
            connection.commit() # 把這個刪掉

            product_data = only_cart()
        
        # 點選繼續購物
        elif "user_edit" in request.form:
            change_order()
                
            return redirect(url_for('bookstore'))
        
        elif "buy" in request.form:

            change_order()

            return redirect(url_for('order'))

        elif "order" in request.form:

            user_id = current_user.id #找到現在使用者是誰
            cursor.prepare('SELECT * FROM CART WHERE MID = :id ')
            cursor.execute(None, {'id': user_id})
            tno = cursor.fetchone()[2] # 交易編號

            cursor.prepare('SELECT SUM(TOTAL) FROM RECORD WHERE TNO=:tno ')
            cursor.execute(None, {'tno': tno})
            total = cursor.fetchone()[0] # 總金額
            
            cursor.prepare('DELETE FROM CART WHERE MID = :id ')
            cursor.execute(None, {'id': user_id})
            connection.commit() # 把這個刪掉

            time = str(datetime.now().strftime('%Y/%m/%d %H:%M:%S'))
            format = 'yyyy/mm/dd hh24:mi:ss'

            cursor.prepare('INSERT INTO ORDER_LIST VALUES ( order2_seq.nextval , :mid, TO_DATE( :time, :format ), :total)')
            cursor.execute(None, {'mid': user_id, 'time':time, 'total':total, 'format':format})
            connection.commit() # 把這個刪掉

            return render_template('complete.html')

    
    product_data = only_cart()
    
    if product_data == 0:
        return render_template('empty.html')
    else:
        return render_template('cart.html', data=product_data)

def add_product():
    user_id = current_user.id #找到現在使用者是誰
    cursor.prepare('SELECT * FROM CART WHERE MID = :id ')
    cursor.execute(None, {'id': user_id})
    data = cursor.fetchone()

    if( data == None): #假如購物車裡面沒有他的資料
        time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.prepare('INSERT INTO CART VALUES (:id, :time, cart_tno_seq.nextval)')
        cursor.execute(None, {'id': user_id, 'time':time})
        connection.commit()
        
        cursor.prepare('SELECT * FROM CART WHERE MID = :id ')
        cursor.execute(None, {'id': user_id})
        data = cursor.fetchone()
    
    tno = data[2] # 使用者有購物車了，購物車的交易編號是什麼
    pid = request.values.get('pid') # 使用者想要購買的東西
    
    cursor.prepare('SELECT * FROM RECORD WHERE PID = :id and TNO = :tno')
    cursor.execute(None, {'id': pid, 'tno':tno})
    product = cursor.fetchone()    

    cursor.prepare('SELECT PRICE FROM PRODUCT WHERE PID = :id ')
    cursor.execute(None, {'id': pid})
    price = cursor.fetchone()[0]

    # 如果購物車裡面沒有的話 把他加一個進去
    if(product == None):
        cursor.prepare('INSERT INTO RECORD VALUES (:id, :tno, 1, :price, :total)')
        cursor.execute(None, {'id': tno, 'tno':pid, 'price':price, 'total':price})
        connection.commit()

    else:
        cursor.prepare('SELECT AMOUNT FROM RECORD WHERE TNO = :id and PID=:pid')
        cursor.execute(None, {'id': tno, 'pid':pid})
        amount = cursor.fetchone()[0]
        total = (amount+1)*int(price)
        cursor.prepare('UPDATE RECORD SET AMOUNT=:amount, TOTAL=:total WHERE PID=:pid and TNO=:tno')
        cursor.execute(None, {'amount':amount+1, 'tno':tno , 'pid':pid, 'total':total})
    
    cursor.prepare('SELECT * FROM RECORD WHERE TNO = :id')
    cursor.execute(None, {'id': tno})
    product_row = cursor.fetchall()
    product_data = []
    for i in product_row:
        cursor.prepare('SELECT PNAME FROM PRODUCT WHERE PID = :id')
        cursor.execute(None, {'id': i[1]})
        price = cursor.fetchone()[0]    
        product = {
            '商品編號': i[1],
            '商品名稱': price,
            '商品價格': i[3],
            '數量': i[2]
        }
        product_data.append(product)
    
    return product_data

def change_order():

    user_id = current_user.id #找到現在使用者是誰
    cursor.prepare('SELECT * FROM CART WHERE MID = :id ')
    cursor.execute(None, {'id': user_id})
    data = cursor.fetchone()

    tno = data[2] # 使用者有購物車了，購物車的交易編號是什麼
    cursor.prepare('SELECT * FROM RECORD WHERE TNO = :id')
    cursor.execute(None, {'id': tno})
    product_row = cursor.fetchall()

    for i in product_row:
        
        # i[0]：交易編號 / i[1]：商品編號 / i[2]：數量 / i[3]：價格
        if int(request.form[i[1]]) != i[2]:
            cursor.prepare('UPDATE RECORD SET AMOUNT=:amount, TOTAL=:total WHERE PID=:pid and TNO=:tno')
            cursor.execute(None, {'amount':request.form[i[1]], 'pid':i[1], 'tno':tno, 'total':int(request.form[i[1]])*int(i[3])})
            connection.commit()
            print('change')

    return 0


def only_cart():
    user_id = current_user.id #找到現在使用者是誰
    cursor.prepare('SELECT * FROM CART WHERE MID = :id ')
    cursor.execute(None, {'id': user_id})
    data = cursor.fetchone()

    if( data == None): #假如購物車裡面沒有他的資料
        
        return 0
    

    tno = data[2] # 使用者有購物車了，購物車的交易編號是什麼
    cursor.prepare('SELECT * FROM RECORD WHERE TNO = :id')
    cursor.execute(None, {'id': tno})
    product_row = cursor.fetchall()
    product_data = []

    for i in product_row:
        cursor.prepare('SELECT PNAME FROM PRODUCT WHERE PID = :id')
        cursor.execute(None, {'id': i[1]})
        price = cursor.fetchone()[0] 
        product = {
            '商品編號': i[1],
            '商品名稱': price,
            '商品價格': i[3],
            '數量': i[2]
        }
        product_data.append(product)
    
    return product_data

@app.route('/manager', methods=['GET', 'POST'])
@login_required
def manager():
    
    if request.method == 'GET':
        if( current_user.role == 'user'):
            flash('No permission')
            return redirect(url_for('bookstore'))

    if 'delete' in request.values: #要刪除

        pid = request.values.get('delete')

        # 看看 RECORD 裡面有沒有需要這筆產品的資料
        cursor.prepare('SELECT * FROM RECORD WHERE PID=:pid')
        cursor.execute(None, {'pid':pid})
        data = cursor.fetchone() #可以抓一筆就好了，假如有的話就不能刪除
        
        if(data != None):
            flash('faild')
        else:
            cursor.prepare('DELETE FROM PRODUCT WHERE PID = :id ')
            cursor.execute(None, {'id': pid})
            connection.commit() # 把這個刪掉

    elif 'edit' in request.values: #要修改
            pid = request.values.get('edit')
            return redirect(url_for('edit', pid=pid))

    book_data = book()

    return render_template('manager.html', book_data=book_data, user=current_user.name)

def book():
    sql = 'SELECT * FROM PRODUCT'
    cursor.execute(sql)
    book_row = cursor.fetchall()
    book_data = []
    for i in book_row:
        book = {
            '商品編號': i[0],
            '商品名稱': i[1],
            '商品售價': i[2],
            '商品類別': i[3]
        }
        book_data.append(book)
    return book_data

@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():

    # 以防使用者使用管理員功能
    if request.method == 'GET':
        if( current_user.role == 'user'):
            flash('No permission')
            return redirect(url_for('bookstore'))

    if request.method == 'POST':
        pid = request.values.get('pid')
        new_name = request.values.get('name')
        new_price = request.values.get('price')
        new_category = request.values.get('category')
        cursor.prepare('UPDATE PRODUCT SET PNAME=:name, PRICE=:price, CATEGORY=:category WHERE PID=:pid')
        cursor.execute(None, {'name':new_name, 'price':new_price,'category':new_category, 'pid':pid})
        connection.commit()
        
        return redirect(url_for('manager'))

    else:
        product = show_info()
        return render_template('edit.html', data=product)


def show_info():
    pid = request.args['pid']
    cursor.prepare('SELECT * FROM PRODUCT WHERE PID = :id ')
    cursor.execute(None, {'id': pid})

    data = cursor.fetchone() #password
    pname = data[1]
    price = data[2]
    category = data[3]

    product = {
        '商品編號': pid,
        '商品名稱': pname,
        '單價': price,
        '類別': category
    }
    return product

@app.route('/add', methods=['GET', 'POST'])
def add():

    if request.method == 'POST':
    
        cursor.prepare('SELECT * FROM PRODUCT WHERE PID=:pid')
        data = ""

        while ( data != None): #裡面沒有才跳出回圈

            number = str(random.randrange( 10000, 99999))
            en = random.choice(string.ascii_letters)
            pid = en + number #隨機編號
            cursor.execute(None, {'pid':pid})
            data = cursor.fetchone()

        name = request.values.get('name')
        price = request.values.get('price')
        category = request.values.get('category')

        if ( len(name) < 1 or len(price) < 1): #使用者沒有輸入
            return redirect(url_for('manager'))

        cursor.prepare('INSERT INTO PRODUCT VALUES (:pid, :name, :price, :category)')
        cursor.execute(None, {'pid': pid, 'name':name, 'price':price, 'category':category })
        connection.commit()

        return redirect(url_for('manager'))

    return render_template('add.html')

@app.route('/order')
def order():

    user_id = current_user.id #找到現在使用者是誰
    cursor.prepare('SELECT * FROM CART WHERE MID = :id ')
    cursor.execute(None, {'id': user_id})
    data = cursor.fetchone()
    
    tno = data[2] # 使用者有購物車了，購物車的交易編號是什麼

    cursor.prepare('SELECT * FROM RECORD WHERE TNO = :id')
    cursor.execute(None, {'id': tno})
    product_row = cursor.fetchall()
    product_data = []

    for i in product_row:
        cursor.prepare('SELECT PNAME FROM PRODUCT WHERE PID = :id')
        cursor.execute(None, {'id': i[1]})
        price = cursor.fetchone()[0] 
        product = {
            '商品編號': i[1],
            '商品名稱': price,
            '商品價格': i[3],
            '數量': i[2]
        }
        product_data.append(product)
    
    cursor.prepare('SELECT SUM(TOTAL) FROM RECORD WHERE TNO = :id')
    cursor.execute(None, {'id': tno})
    total = cursor.fetchone()[0]

    return render_template('order.html', data=product_data, total=total)

@app.route('/dashboard')
@login_required
def dashboard():
    revenue = []
    dataa = []
    for i in range(1,13):
        cursor.prepare('SELECT EXTRACT(MONTH FROM ORDERTIME), SUM(PRICE) FROM ORDER_LIST WHERE EXTRACT(MONTH FROM ORDERTIME)=:mon GROUP BY EXTRACT(MONTH FROM ORDERTIME)')
        cursor.execute(None, {"mon": i})
        
        row = cursor.fetchall()
        if cursor.rowcount == 0:
            revenue.append(0)
        else:
            for j in row:
                revenue.append(j[1])
                
        cursor.prepare('SELECT EXTRACT(MONTH FROM ORDERTIME), COUNT(OID) FROM ORDER_LIST WHERE EXTRACT(MONTH FROM ORDERTIME)=:mon GROUP BY EXTRACT(MONTH FROM ORDERTIME)')
        cursor.execute(None, {"mon": i})
        
        row = cursor.fetchall()
        if cursor.rowcount == 0:
            dataa.append(0)
        else:
            for k in row:
                dataa.append(k[1])
        
    cursor.prepare('SELECT SUM(TOTAL), CATEGORY FROM(SELECT * FROM PRODUCT,RECORD WHERE PRODUCT.PID = RECORD.PID) GROUP BY CATEGORY')
    cursor.execute(None)
    row = cursor.fetchall()
    datab = []
    for i in row:
        temp = {
            'value': i[0],
            'name': i[1]
        }
        datab.append(temp)
    
    cursor.prepare('SELECT SUM(PRICE), MEMBER.MID, MEMBER.NAME FROM ORDER_LIST, MEMBER WHERE ORDER_LIST.MID = MEMBER.MID AND MEMBER.IDENTITY = :identity AND ROWNUM<=5 GROUP BY MEMBER.MID, MEMBER.NAME ORDER BY SUM(PRICE) DESC')
    cursor.execute(None, {'identity':'user'})
    row = cursor.fetchall()
    
    datac = []
    nameList = []
    counter = 0
    
    for i in row:
        counter = counter + 1
        datac.append(i[0])
    for j in row:
        nameList.append(j[2])
    
    counter = counter - 1
    
    cursor.prepare('SELECT COUNT(*), MEMBER.MID, MEMBER.NAME FROM ORDER_LIST, MEMBER WHERE ORDER_LIST.MID = MEMBER.MID AND MEMBER.IDENTITY = :identity AND ROWNUM<=5 GROUP BY MEMBER.MID, MEMBER.NAME ORDER BY COUNT(*) DESC')
    cursor.execute(None, {'identity':'user'})
    row = cursor.fetchall()
    
    countList = []
    
    for i in row:
        countList.append(i[0])
        
    return render_template('dashboard.html', counter = counter, revenue = revenue, dataa = dataa, datab = datab, datac = datac, nameList = nameList, countList = countList)

@app.route('/logout')  
def logout():

    logout_user()  
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.debug = True #easy to debug
    app.secret_key = "Your Key"
    app.run()