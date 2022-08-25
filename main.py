import sqlite3

from string import ascii_letters, digits
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, g, session, request, flash
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import BadRequestKeyError


SECRET_KEY = "\xd4\xd9`~\x002\x03\xe4f\xa8\xd3Q\xb0\xbc\xf4w\xd5\x8e\xa6\xd5\x940\xf5\x8d\xbd\xefH\xf2\x8cPQ$\x04\xea\xc7cWA\xc7\xf6Rn6\xa8\x89\x92\xbf%*\xcd\x03j\x1e\x8ei?x>\n:~+(Z"
USERNAME_WHITELIST = set(ascii_letters + digits + "_")
CATEGORIES = {
    "1" : "General",
    "2" : "Help",
    "3" : "Lore",
    "4" : "Humor",
    "5" : "News"
}
SORT = {
    "1":"like",
    "2":"dislike"
}


# Store database connection in a variable
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect("forum_database.db")
    return g.db


# Easy function to get today's date
def today():
    # Format is YYYYMMDD with leading zeros for months and days
    # This allows for easy sort by date and string splicing
    today = datetime.today().strftime("%Y%m%d")
    return today


# Gather the information for forum posts from the database.
# String building may be required in a later date
# All results will be stored as a tuple in a list
# For single item lists, specify with a index of 0
def call_database(query, parameter=None):
    conn = get_db()
    cur = conn.cursor()
    # Can't have option arguments in .execute function
    # May use string building in the future
    try:
        cur.execute(query, parameter)
    except (sqlite3.Warning) as e:
        cur.executescript(query)
    except (sqlite3.ProgrammingError, ValueError) as e:
        cur.execute(query)
    result = cur.fetchall()
    return result


"""
DO NOT USE WITH CUSTOM USER INPUT
"""
# Create query to present data
def build_query(type, user_id, category="", order="", reply=None, post_id=None):
    if type == "p":
        if user_id:
            graded_post = f"LEFT JOIN PostGrade AS UserGrade ON UserGrade.post_id = Post.id AND UserGrade.user_id = {user_id}"
            user_grade = "UserGrade.grade"
        else:
            graded_post = ""
            user_grade = "NULL"
        final_query = f"""
        SELECT Post.*,
        SUM(CASE WHEN PostGrade.grade = -1 THEN 1 ELSE 0 END) AS dislike,
        SUM(CASE WHEN PostGrade.grade = 1 THEN 1 ELSE 0 END) AS like,
        User.username,
        (SELECT COUNT(Comment.id) FROM Comment WHERE Comment.post_id = Post.id) AS comment_count,
        {user_grade}
        FROM Post
        INNER JOIN User ON Post.user_id = User.id
        LEFT JOIN PostGrade ON PostGrade.post_id = Post.id {graded_post} 
        {category} GROUP BY Post.id {order};"""
    elif type == "c":
        if user_id:
            graded_post = f"LEFT JOIN CommentGrade AS UserGrade ON UserGrade.comment_id = Comment.id AND UserGrade.user_id = {user_id}"
            user_grade = "UserGrade.grade"
        else:
            graded_post = ""
            user_grade = "NULL"
        if reply:
            reply = " AND Comment.parent_comment_id IS NOT NULL"
        else:
            reply = " AND Comment.parent_comment_id IS NULL"
        final_query = f"""
        SELECT Comment.*,
        SUM(CASE WHEN CommentGrade.grade = -1 THEN 1 ELSE 0 END) AS dislike,
        SUM(CASE WHEN CommentGrade.grade = 1 THEN 1 ELSE 0 END) AS like,
        User.username,
        {user_grade}
        FROM Comment
        INNER JOIN User ON Comment.user_id = User.id
        LEFT JOIN CommentGrade ON CommentGrade.comment_id = Comment.id {graded_post} 
        WHERE Comment.post_id = ? {reply}
        GROUP BY Comment.id;"""
    else:
        raise Exception(f"type {type} is invalid, must be 'c' or 'p'")
    if post_id:
        parameter = (post_id,)
    else:
        parameter = tuple()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(final_query, parameter)
    result = cur.fetchall()
    return result


# Delete entry in database function
"""
DO NOT USE FOR USER INPUT
"""
def delete_entry(type, id):
    conn = get_db()
    cur = conn.cursor()
    if type == "p":
        first = "DELETE FROM Post"
    elif type == "c":
        first = "DELETE FROM Comment"
    elif type == "u":
        first = "DELETE FROM User"
    else:
        raise Exception(f"{type} is an invalid type")
    cur.execute(f"{first} WHERE id = ?", (id,))
    conn.commit()


# Updates Post table once user submits new post
def update_post(type, title, content, date, user_id,):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO Post
                (type, title, content, user_id, date)
                VALUES (?, ?, ?, ?, ?)""",
                (type, title, content, user_id, date))
    conn.commit()


# Updates comments table once user creates a comment or reply
# like and dislike cannot be null so default value is 0
def update_comment(user_id, post_id, content, date, parent_comment_id=None,):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO Comment
                (user_id, post_id, parent_comment_id, content, date)
                VALUES (?, ?, ?, ?, ?)""",
                (user_id, post_id, parent_comment_id, content, date))
    conn.commit()


# Insert user data into database
def create_user(username, date, password_hash):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO User
                (username, credit, is_admin, join_date, password_hash)
                VALUES (?, 0, False, ?, ?)""",
                (username, date, password_hash))
    conn.commit()


# Verify grade of user
def add_grade(user_id, type, type_id, grade, replace=None):
    conn = get_db()
    cur = conn.cursor()
    # Add new grade 
    if not replace:
        if type == "p":
            query = "INSERT INTO PostGrade (user_id, post_id, grade) VALUES (?, ?, ?)" 
        elif type == "c":
            query = "INSERT INTO CommentGrade (user_id, comment_id, grade) VALUES (?, ?, ?)"
        parameter = (user_id, type_id, grade)
    # Replace existing grade
    elif replace:
        if type == "p":
            query = "UPDATE PostGrade SET grade = ? WHERE user_id = ? AND post_id = ?"
        elif type == "c":
            query = "UPDATE CommentGrade SET grade = ? WHERE user_id = ? AND comment_id = ?"
        parameter = (grade, user_id, type_id)
    print(query)
    cur.execute(query, parameter)
    conn.commit()


# Update user credit when displayed
def update_credit(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""SELECT
                SUM(CASE WHEN PostGrade.grade IS NULL THEN 0 ELSE PostGrade.grade END) AS post_credit
                FROM PostGrade WHERE user_id = ?""",
                (user_id,))
    post_credit = cur.fetchone()[0]
    cur.execute("""SELECT
                SUM(CASE WHEN CommentGrade.grade IS NULL THEN 0 ELSE CommentGrade.grade END) AS comment_credit
                FROM CommentGrade WHERE user_id = ?""",
                (user_id,))
    comment_credit = cur.fetchone()[0]
    print(comment_credit)
    print(post_credit)
    total_credit = int(post_credit or 0) + int(comment_credit or 0)
    print(total_credit)
    cur.execute("UPDATE User SET credit = ? WHERE id = ?", (total_credit, user_id))
    conn.commit()


"""
Flask app starts below
"""


app = Flask(__name__)
CSRFProtect().init_app(app)
app.secret_key = SECRET_KEY


# The post tables gets passed to the jinja loop in "home.html".
# This is to create HTML posts for each entry in the post table.
@app.route("/")
def home():
    # raise Exception("idot")
    user_id = session.get("user_id", None)
    selected_category = session.get("category", None)
    selected_order = session.get("order", None)
    # Check for sorting
    if selected_category:
        where = f"WHERE Post.type = '{CATEGORIES[selected_category]}'"
    else:
        where = ""
    if selected_order:
        order_by = f"ORDER BY {SORT[selected_order]} DESC"
    else:
        order_by = f"ORDER BY id DESC"
    post = build_query("p", user_id, where, order_by)
    return render_template("home.html", post=post, title="Home")


# The route creates pages dynamically.
# The id variable passed into the call database function.
# Page info is passed into HTML with jinja code
@app.route("/page/<int:id>")
def page(id):
    user_id = session.get("user_id", None)
    post = build_query(user_id=user_id, type="p", category="WHERE Post.id = ?", post_id=id)[0]
    comment = build_query(user_id=user_id, type="c", category="WHERE post_id = ? AND parent_comment_id IS NULL", post_id=id)
    reply = build_query(user_id=user_id, type="c", category="WHERE post_id = ? AND parent_comment_id IS NOT NULL", post_id=id, reply=True)
    return render_template("page.html",
                           post=post,
                           comment=comment,
                           reply=reply,
                           title=post[2]) # Post Title


# Page where user replies to a comment.
@app.route("/page/reply_to/<int:post_id>/<int:comment_id>")
def reply_to(post_id, comment_id):
    reffered_comment = call_database("""SELECT * FROM Comment
                                     WHERE id = ?
                                     AND post_id = ?""",
                                     (comment_id, post_id))[0]
    return render_template("reply.html", comment=reffered_comment, title="Reply To")


# Directs user to the about page
@app.route("/about")
def about():
    return render_template("about.html", title="About")


# Redirect user to either sign in or sign up page.
@app.route("/account/<action>")
def account(action):
    # Capitalise first letter and remove underscore
    page_title = f"{action[0].upper()}{action[1:4]} {action[5].upper()}{action[6:]}"
    return render_template("sign.html", page=action, title=page_title)


# Goes to account manager
# Calls any relevant database entries
@app.route("/account_management/<int:id>")
def dashboard(id):
    user_id = session.get("user_id", None)
    user_post = call_database("SELECT * FROM Post WHERE user_id = ?", (id,))
    user_info = call_database("SELECT * FROM User WHERE id = ?", (id,))[0]
    # if user is deleted, redirect error
    update_credit(id)
    return render_template("user.html", user_info=user_info, user_post=user_post, id=id, title=user_info[1], user_id=user_id)


# 400 error 
@app.errorhandler(CSRFError)
def validation_error(e):
    return render_template("400.html"), 400 


# 404 error
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


# 500 error
@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500


# Gets the form values from the home page,
# The variables get updated to the database.
@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        type = request.form.get("type")
        date = today()
        update_post(type, title, content, date, session.get("user_id"))
        # Go back to home page so users can easily see their new post
    return redirect(request.referrer)


# Gets values from each created comment
# Update comment database using given values
# refresh current page
@app.route("/create_comment", methods=["GET", "POST"])
def create_comment():
    if request.method == "POST":
        content = request.form.get("comment_content")
        post_id = request.form.get("post_id")
        date = today()
        update_comment(session.get("user_id"), post_id, content, date)
    return redirect(request.referrer)


# Update database with reply    
@app.route("/reply", methods=["GET", "POST"])
def reply():
    if request.method == "POST":
        content = request.form.get("content")
        post_id = request.form.get("post_id")
        comment_id = request.form.get("comment_id")
        date = today()
        update_comment(session.get("user_id"), post_id, content, date, comment_id)
        return redirect(url_for("page", id=post_id))
    return request.referrer


# Update post or comment with like or dislike.
@app.route("/grade/<int:id>/", methods=["GET", "POST"])
def grade(id):
    grade_to_int = {
        "Like" : 1,
        "Dislike" : -1
    }
    if not session.get("user_id", None ):
        flash("Create an account to like or dislike", "info")
        return redirect(url_for("account", action="sign_up"))
    
    if request.method == "POST":
        user_id = session.get("user_id", None)
        table = request.form.get("table")
        grade = grade_to_int.get(request.form.get("grade"))
        # Find if user already liked or disliked post/comment
        if table == "p":
            query = "SELECT grade FROM PostGrade WHERE user_id = ? AND post_id = ?"
        elif table == "c":
            query = "SELECT grade FROM CommentGrade WHERE user_id = ? AND comment_id = ?"
        existing_grade = call_database(query, (user_id, id))
        # Prevent user for giving the same grade to posts/comments Otherwise give grade.
        if not existing_grade:
            add_grade(user_id, table, id, grade)
        # Change grade 
        elif existing_grade[0][0] != grade:
            add_grade(user_id, table, id, grade, True)
        # Build url No section exception
        try:
            section = request.form.get("section")
            url = request.referrer + f"#{str(section)}"
        except BadRequestKeyError:
            url = request.referrer
    else:
        url = request.referrer
    return redirect(url)
            

# Creates user account and adds to the database
# Password is salted and hashed
@app.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        date = today()
        # Check for invalid characters
        if not all(u_letter in USERNAME_WHITELIST for u_letter in username):
            flash("Usernames can only contain A-Z, 0-9, and '_'", "error")
        # Get existing usernames then converts result into list without single element tuples
        existing_usernames = [i[0] for i in call_database("SELECT username FROM User")]
        if username not in existing_usernames:
            create_user(username, date, (generate_password_hash(password, salt_length=16)))
            flash("Account created, log in to access your account", "info")
            return redirect(url_for("account", action="sign_in"))
        else:
            flash("That username already exists", "error")
        return redirect(request.referrer)


# Activates user session if user sucessfuly logs in
@app.route("/sign_in", methods=["GET", "POST"])
def sign_in():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user_info = call_database("SELECT id, username, password_hash FROM User WHERE username = ?", (username,)) 
        if not user_info:
            flash("Username or password is incorrect", "error")
            return redirect(request.referrer)
        user_info = user_info[0]
        if not check_password_hash(user_info[2], password):
            flash("Username or password is incorrect", "error")
            return redirect(request.referrer)
        else:
            session["user_id"] = user_info[0]
            flash(f"Logged in successfully as {username}", "info")
    return redirect(url_for("home"))


# Filter posts
@app.route("/sort/<type>", methods=["GET", "POST"])
def sort(type):
    if request.method == "POST":
        if type == "sort":
            session["category"] = request.form.get("type")
        elif type == "order":
            session["order"] = request.form.get("order")
    return redirect(request.referrer)


# Log user out
@app.route("/sign_out")
def sign_out():
    session.pop("user_id", None)
    flash("Successfully logged out", "info")
    return redirect(url_for("home"))


# Delete user, post, or comment
@app.route("/delete", methods=["GET", "POST"])
def delete():
    if request.method == "POST":
        id = request.form.get("id")
        type = request.form.get("type")
        if type == "u":
            session.pop("user_id", None)
            url = url_for("home")
        else:
            url = request.referrer
        delete_entry(type, id)
    return redirect(url)


# Close database once app is closed.
@app.teardown_appcontext
def teardown_db(_):
    get_db().close()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port="8000")
