import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


# 
app = Flask(__name__)
app.secret_key = "\xd4\xd9`~\x002\x03\xe4f\xa8\xd3Q\xb0\xbc\xf4w\xd5\x8e\xa6\xd5\x940\xf5\x8d\xbd\xefH\xf2\x8cPQ$\x04\xea\xc7cWA\xc7\xf6Rn6\xa8\x89\x92\xbf%*\xcd\x03j\x1e\x8ei?x>\n:~+(Z"


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
    if parameter is None:
        cur.execute(query)
    else:
        cur.execute(query, parameter)
    result = cur.fetchall()
    return result


# Updates Post table once user submits new post
def update_post(type, title, content, date, user_id, like=0, dislike=0):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO Post
                (type, title, content, like, dislike, user_id, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (type, title, content, like, dislike, user_id, date))
    conn.commit()


# Updates comments table once user creates a comment or reply
# like and dislike cannot be null so default value is 0
def update_comment(user_id, post_id, content, date, comment_id=None, like=0, dislike=0):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO Comment
                (user_id, post_id, comment_id, content, like, dislike, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, post_id, comment_id, content, like, dislike, date))
    conn.commit()


# Incriment the like or dislike counter by one.
# Parameters can't be used to pass table or column names
# So string building must be user to update certain parts of the database depending on the conditions.
# This query must never be user on other occasions; only on the update grade route
def update_grade(table, grade, id):
    conn = get_db()
    cur = conn.cursor()
    conn.set_trace_callback(print)
    if table.lower() == "post":
        first = "UPDATE Post SET"
    elif table.lower() == "comment":
        first = "UPDATE Comment SET"
    if grade.lower() == "like":
        last = "like = like + 1 WHERE id = ?"
    if grade.lower() == "dislike":
        last = "dislike = dislike + 1 WHERE id = ?"
    print(f"{first} {last}")
    cur.execute(f"{first} {last}", (id,))
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


# Flask app starts below


# The post tables gets passed to the jinja loop in "home.html".
# This is to create HTML posts for each entry in the post table.
@app.route("/")
def home():
    post = call_database("SELECT * FROM Post")
    return render_template("home.html", post=post)


# The route creates pages dynamically.
# The id variable passed into the call database function.
# Page info is passed into HTML with jinja code
@app.route("/page/<int:id>")
def page(id):
    # Page_info needs index of 0 as the result is stored in tuple inside a list
    page_info = call_database("SELECT * FROM Post WHERE id = ?", (str(id)),)[0]
    # Comments tied to posts have no comment_id
    comment = call_database("""SELECT * FROM Comment
                            WHERE comment_id IS NULL
                            AND post_id = ?""",
                            (str(id)),)
    # Replies are tied to a comment so theres a comment_id
    reply = call_database("""SELECT * FROM Comment
                          WHERE comment_id IS NOT NULL
                          AND post_id = ?""",
                          (str(id)),)
    return render_template("page.html",
                           page=page_info,
                           comment=comment,
                           reply=reply)


# Page where user replies to a comment.
@app.route("/page/reply_to/<int:post_id>/<int:comment_id>")
def reply_to(post_id, comment_id):
    reffered_comment = call_database("""SELECT * FROM Comment
                                     WHERE id = ?
                                     AND post_id = ?""",
                                     (comment_id, post_id))[0]
    return render_template("reply.html", comment=reffered_comment)


# Directs user to the about page
@app.route("/about")
def about():
    return render_template("about.html")


# A page exclusively to search for specific posts.
@app.route("/search")
def search():
    return render_template("search.html")


# Redirect user to either sign in or sign up page.
@app.route("/sign/<action>")
def sign(action):
    return render_template("sign.html", page=action)


# Gets the form values from the home page,
# The variables get updated to the database.
@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        type = request.form["type"]
        date = today()
        update_post(type, title, content, date, 1)
        # Go back to home page so users can easily see their new post
        return redirect(request.referrer)
 

# Gets values from each created comment
# Update comment database using given values
# refresh current page
@app.route("/create_comment", methods=["GET", "POST"])
def create_comment():
    if request.method == "POST":
        content = request.form["comment_content"]
        post_id = request.form["post_id"]
        date = today()
        update_comment(1, post_id, content, date)
        return redirect(request.referrer)


# Update database with reply
@app.route("/reply", methods=["GET", "POST"])
def reply():
    if request.method == "POST":
        content = request.form["content"]
        post_id = request.form["post_id"]
        comment_id = request.form["comment_id"]
        date = today()
        update_comment(1, post_id, content, date, comment_id)
        return redirect(url_for("page", id=post_id))


# Update post or comment with like or dislike.
@app.route("/grade/<int:id>/", methods=["GET", "POST"])
def grade(id):
    if request.method == "POST":
        table = request.form["table"]
        grade = request.form["grade"]
        update_grade(table, grade, id)
        return redirect(request.referrer)


# Creates user account and adds to the database
# Password is salted and hashed
@app.route("/sign_up", methods=["GET","POST"])
def sign_up():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        date = today()
        create_user(username, date, (generate_password_hash(password, salt_length=16)))

        return redirect(url_for("sign", action="sign_in"))


# Users are signed in if username and password matches
@app.route("/sign_in", methods=["GET", "POST"])
def log_in():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user_info = call_database("""SELECT id, username, password_hash FROM User WHERE username = ?""", (username,))[0]
        if check_password_hash(user_info[2], password):
            session["user_id"] = user_info[0]       
        return redirect(url_for("home"))


# Close database once app is closed.
@app.teardown_appcontext
def teardown_db(_):
    get_db().close()


# Only run if not imported
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port="8000")
