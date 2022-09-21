"""
The Roundtable Hold a forum for Elden Ring players, by an Elden Ring player
A Website for a 12DTP project
"""
import sqlite3
from string import ascii_letters, digits
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, g, session, request, flash, abort
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import BadRequestKeyError


SECRET_KEY = "d780a9cw7379b1993158bb7251c5d83b23d97068abe90042ae502d8f256a301366fc78af50ab7cc5621e7"
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


def get_db():
    """Store database connection in a variable"""
    if "db" not in g:
        g.db = sqlite3.connect("forum_database.db")
    return g.db


def today():
    """Easy function to get today's date"""
    # Format is YYYYMMDD with leading zeros for months and days
    # This allows for easy sort by date and string splicing
    post_date = datetime.today().strftime("%Y%m%d")
    return post_date


# Gather the information for forum posts from the database.
# String building may be required in a later date
# All results will be stored as a tuple in a list
# For single item lists, specify with a index of 0
def call_database(query, parameter=None):
    """Simple function to get database"""
    conn = get_db()
    cur = conn.cursor()
    # Can't have option arguments in .execute function
    # May use string building in the future
    try:
        cur.execute(query, parameter)
    except sqlite3.Warning:
        cur.executescript(query)
    except sqlite3.ProgrammingError:
        cur.execute(query)
    except ValueError:
        cur.execute(query)
    result = cur.fetchall()
    return result


# Create query to present data
def build_query(type, user_id, condition="", order="", reply=None, post_id=None):
    """
    DO NOT USE WITH CUSTOM USER INPUT
    """
    if type == "p":
        if user_id:
            query, parameter = f"""SELECT Post.*,
            SUM(CASE WHEN PostGrade.grade = -1 THEN 1 ELSE 0 END) AS dislike,
            SUM(CASE WHEN PostGrade.grade = 1 THEN 1 ELSE 0 END) AS like,
            User.username,
            (SELECT COUNT(Comment.id) FROM Comment WHERE Comment.post_id = Post.id) AS comment_count,
            UserGrade.grade
            FROM Post
            INNER JOIN User ON Post.user_id = User.id
            LEFT JOIN PostGrade ON PostGrade.post_id = Post.id
            LEFT JOIN PostGrade AS UserGrade ON UserGrade.post_id = Post.id AND UserGrade.user_id = ?
            {condition} GROUP BY Post.id {order};""", [user_id]
        else:
            query, parameter = f"""SELECT Post.*,
            SUM(CASE WHEN PostGrade.grade = -1 THEN 1 ELSE 0 END) AS dislike,
            SUM(CASE WHEN PostGrade.grade = 1 THEN 1 ELSE 0 END) AS like,
            User.username,
            (SELECT COUNT(Comment.id) FROM Comment WHERE Comment.post_id = Post.id) AS comment_count
            FROM Post
            INNER JOIN User ON Post.user_id = User.id
            LEFT JOIN PostGrade ON PostGrade.post_id = Post.id
            {condition} GROUP BY Post.id {order};""", []
    elif type == "c":
        if reply:
            reply = " AND Comment.parent_comment_id IS NOT NULL"
        else:
            reply = " AND Comment.parent_comment_id IS NULL"
        if user_id: 
            query, parameter = f"""SELECT Comment.*,
            SUM(CASE WHEN CommentGrade.grade = -1 THEN 1 ELSE 0 END) AS dislike,
            SUM(CASE WHEN CommentGrade.grade = 1 THEN 1 ELSE 0 END) AS like,
            User.username,
            UserGrade.grade
            FROM Comment
            INNER JOIN User ON Comment.user_id = User.id
            LEFT JOIN CommentGrade ON CommentGrade.comment_id = Comment.id 
            LEFT JOIN CommentGrade AS UserGrade ON UserGrade.comment_id = Comment.id AND UserGrade.user_id = ?
            WHERE Comment.post_id = ?
            {reply}
            GROUP BY Comment.id;""", [user_id]
        else:
            query, parameter = f"""SELECT Comment.*,
            SUM(CASE WHEN CommentGrade.grade = -1 THEN 1 ELSE 0 END) AS dislike,
            SUM(CASE WHEN CommentGrade.grade = 1 THEN 1 ELSE 0 END) AS like,
            User.username
            FROM Comment
            INNER JOIN User ON Comment.user_id = User.id
            LEFT JOIN CommentGrade ON CommentGrade.comment_id = Comment.id 
            WHERE Comment.post_id = ? 
            {reply}
            GROUP BY Comment.id;""", []
    else:
        raise Exception(f"type {type} is invalid, must be 'c' or 'p'")
    if post_id:
        parameter.append(post_id)
    parameter = tuple(parameter)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, parameter)
    result = cur.fetchall()
    return result


# Delete entry in database function
def delete_entry(delete_type, id):
    """
    DO NOT USE FOR USER INPUT
    """
    conn = get_db()
    cur = conn.cursor()
    if delete_type == "p":
        first = "DELETE FROM Post"
    elif delete_type == "c":
        first = "DELETE FROM Comment"
    elif delete_type == "u":
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
                (username, is_admin, join_date, password_hash)
                VALUES (?, False, ?, ?)""",
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
    cur.execute(query, parameter)
    conn.commit()


# Update user credit when displayed
def user_credit(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""SELECT Post.id AS post_id, SUM(PostGrade.grade) FROM Post
                INNER JOIN PostGrade ON PostGrade.post_id = Post.id
                WHERE Post.user_id = ?;""",
                (user_id,))
    post_credit = cur.fetchone()[1]
    cur.execute("""SELECT Comment.id AS comment_id, SUM(CommentGrade.grade) FROM Comment
                INNER JOIN CommentGrade ON CommentGrade.comment_id = Comment.id
                WHERE Comment.user_id = ?;""",
                (user_id,))
    comment_credit = cur.fetchone()[1]
    return int(post_credit or 0) + int(comment_credit or 0)


app = Flask(__name__)
app.secret_key = SECRET_KEY


# The post tables gets passed to the jinja loop in "home.html".
# This is to create HTML posts for each entry in the post table.
@app.route("/")
def home():
    # raise Exception("idot") # test 500 error
    user_id = session.get("user_id", None)
    condition = session.get("category", None)
    order_by = session.get("order", None)
    # Check for sorting
    if condition:
        condition = f"WHERE Post.type = '{CATEGORIES[condition]}'"
    else:
        condition = ""
    if order_by:
        order_by = (f"ORDER BY {SORT[order_by]} DESC")
    else:
        order_by = f"ORDER BY id DESC"
    post = build_query("p", user_id, condition, order_by)
    return render_template("home.html", post=post, title="Home")


# The route creates pages dynamically.
# The id variable passed into the call database function.
# Page info is passed into HTML with jinja code
@app.route("/page/<int:id>")
def page(id):
    user_id = session.get("user_id", None)
    try:
        post = build_query("p", user_id, condition="WHERE Post.id = ?", post_id=id)[0]
    except IndexError:
        abort(404)
    comment = build_query("c", user_id, post_id=id)
    reply = build_query("c", user_id, post_id=id, reply=True)
    return render_template("page.html",
                           post=post,
                           comment=comment,
                           reply=reply,
                           title=post[2]) # Post Title


# Page where user replies to a comment.
@app.route("/page/reply_to/<int:post_id>/<int:comment_id>")
def reply_to(post_id, comment_id):
    try:
        reffered_comment = call_database("""SELECT * FROM Comment
                                        WHERE id = ?
                                        AND post_id = ?""",
                                        (comment_id, post_id))[0]
    except IndexError:
        abort(404)
    return render_template("reply.html", comment=reffered_comment, title="Reply To")


# Directs user to the about page
@app.route("/about")
def about():
    return render_template("about.html", title="About")


# Redirect user to either sign in or sign up page.
@app.route("/account/<action>")
def account(action):
    # Capitalise first letter and remove underscore
    try:
        page_title = f"{action[0].upper()}{action[1:4]} {action[5].upper()}{action[6:]}"
    except IndexError:
        abort(404)
    return render_template("sign.html", page=action, title=page_title)


# Goes to account manager
# Calls any relevant database entries
@app.route("/account_management/<int:id>")
def dashboard(id):
    user_id = session.get("user_id", None)
    user_post = call_database("SELECT * FROM Post WHERE user_id = ?", (id,))
    try:
        user_info = call_database("SELECT * FROM User WHERE id = ?", (id,))[0]
    except IndexError:
        abort(404)
    # if user is deleted, redirect error
    return render_template("user.html",
                            user_info=user_info,
                            user_post=user_post,
                            id=id,
                            title=user_info[1],
                            user_id=user_id,
                            user_credit=user_credit(id))


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
    else:
        return redirect(url_for("home"))


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
    else:
        return redirect(url_for("home"))


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
    else:
        return redirect(url_for("home"))


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
        if grade == None:
            return redirect(request.referrer)
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
        return redirect(url)
    else:
        return redirect(url_for("home"))
            

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
            return redirect(request.referrer)
        # Get existing usernames then converts result into list without single element tuples
        existing_usernames = [i[0] for i in call_database("SELECT username FROM User")]
        if username not in existing_usernames:
            create_user(username, date, (generate_password_hash(password, salt_length=16)))
            flash("Account created, log in to access your account", "info")
            return redirect(url_for("account", action="sign_in"))
        else:
            flash("That username already exists", "error")
            return redirect(request.referrer)
    else:
        return redirect(url_for("home"))


# Activates user session if user sucessfuly logs in
@app.route("/sign_in", methods=["GET", "POST"])
def sign_in():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user_info = call_database("SELECT id, username, password_hash, is_admin FROM User WHERE username = ?", (username,)) 
        if not user_info:
            flash("Username or password is incorrect", "error")
            return redirect(request.referrer)
        user_info = user_info[0]
        if not check_password_hash(user_info[2], password):
            flash("Username or password is incorrect", "error")
            return redirect(request.referrer)
        else:
            session["user_id"] = user_info[0]
            session["admin"] = user_info[3]
            flash(f"Logged in successfully as {username}", "info")
            if session.get("admin", None) == 1:
                flash("You account has admin privileges", "info")
        return redirect(url_for("home"))
    else:
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
    else:
        return redirect(url_for("home"))


# Log user out
@app.route("/sign_out")
def sign_out():
    session.pop("user_id", None)
    session.pop("admin", None)
    flash("Successfully logged out", "info")
    return redirect(url_for("home"))


# Delete user, post, or comment
@app.route("/delete", methods=["GET", "POST"])
def delete():
    if request.method == "POST":
        id = request.form.get("id")
        type = request.form.get("type")
        url = request.referrer
        if type == "u":
            session.pop("user_id", None)
            url = url_for("home")
            flash("Account has been deleted successfuly", "info")
        elif type == "p":
            flash("Post has been deleted", "info")
        delete_entry(type, id)
        return redirect(url)
    else:
        return redirect(url_for("home"))


# Close database once app is closed.
@app.teardown_appcontext
def teardown_db(_):
    get_db().close()


if __name__ == "__main__":
    CSRFProtect().init_app(app)
    app.run(debug=False, host="0.0.0.0", port="8000")
