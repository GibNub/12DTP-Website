import sqlite3
import re
from turtle import title
from flask import *
import werkzeug
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


app = Flask(__name__)
app.secret_key = "\xd4\xd9`~\x002\x03\xe4f\xa8\xd3Q\xb0\xbc\xf4w\xd5\x8e\xa6\xd5\x940\xf5\x8d\xbd\xefH\xf2\x8cPQ$\x04\xea\xc7cWA\xc7\xf6Rn6\xa8\x89\x92\xbf%*\xcd\x03j\x1e\x8ei?x>\n:~+(Z"
default_title = "The Roundtable Hold"


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
    conn.set_trace_callback(print)
    cur = conn.cursor()
    # Can't have option arguments in .execute function
    # May use string building in the future
    try:
        cur.execute(query, parameter)
    except (sqlite3.ProgrammingError, ValueError) as e:
        cur.execute(query)
    result = cur.fetchall()
    return result


# Delete entry in database function
def delete_entry(type, id):
    conn = get_db()
    cur = conn.cursor()
    if type == "post":
        first = "DELETE FROM Post"
    elif type == "comment":
        first = "DELETE FROM Comment"
    elif type == "user":
        first = "DELETE FROM User"
    cur.execute(f"{first} WHERE id = ?", (id,))
    conn.commit()


# Updates Post table once user submits new post
def update_post(type, title, content, date, user_id, like=0, dislike=0):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO Post
                (type, title, content, like, dislike, user_id, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (type, title, content, like, dislike, user_id, date))
    conn.commit()


# Verify grade of user
def graded(user_id, type, type_id, grade, replace=None):
    conn = get_db()
    cur = conn.cursor()
    # Add new grade 
    if not replace:
        if type == "Post":
            query = "INSERT INTO Graded (user_id, post_id, grade) VALUES (?, ?, ?)" 
        elif type == "Comment":
            query = "INSERT INTO Graded (user_id, comment_id, grade) VALUES (?, ?, ?)"
        parameter = (user_id, type_id, grade)
    # Replace existing grade
    elif replace:
        if type == "Post":
            query = "UPDATE Graded SET grade = ? WHERE user_id = ? AND post_id = ?"
        elif type == "Comment":
            query = "UPDATE Graded SET grade = ? WHERE user_id = ? AND post_id = ?"
        parameter = (grade, user_id, type_id)
    cur.execute(query, parameter)
    conn.commit()


# Incriment the like or dislike counter by one.
# Parameters can't be used to pass table or column names
# So string building must be user to update certain parts of the database depending on the conditions.
# This query must never be user on other occasions; only on the update grade route
# Old Code Below
# def update_grade(table, grade, id, grade_exist):
#     conn = get_db()
#     cur = conn.cursor()
#     if not grade_exist:
#         if table.lower() == "post":
#             first = "UPDATE Post SET"
#         elif table.lower() == "comment":
#             first = "UPDATE Comment SET"
#         if grade.lower() == "like":
#             last = "like = like + 1 WHERE id = ?"
#         elif grade.lower() == "dislike":
#             last = "dislike = dislike + 1 WHERE id = ?"
#     cur.execute(f"{first} {last}", (id,))
#     conn.commit()
def update_grade(id, type):
    conn = get_db()
    cur = conn.cursor()
    if type == "Post":
        query = "SELECT grade FROM Graded WHERE post_id = ?"
        update_counter_query = "UPDATE Post SET like = ?, dislike = ? WHERE id = ?"
    elif type == "Comment":
        query = "SELECT grade FROM Graded WHERE comment_id = ?"
        update_counter_query = "UPDATE Comment SET like = ?, dislike = ? WHERE id = ?"
    cur.execute(query, (id,))
    result = cur.fetchall()
    result = [i[0] for i in result]
    likes = result.count("Like")
    dislikes = result.count("Dislike")
    cur.execute(update_counter_query, (likes, dislikes, id))
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


# Insert user data into database
def create_user(username, date, password_hash):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO User
                (username, credit, is_admin, join_date, password_hash)
                VALUES (?, 0, False, ?, ?)""",
                (username, date, password_hash))
    conn.commit()


# Changes user credit in databasea
def credit_update(user_id):
    conn = get_db()
    cur = conn.cursor()
    # Defaults any none values into zero
    post_credit = int(call_database("SELECT SUM(like) - SUM(dislike) FROM Post WHERE user_id = ?",
                     (user_id,))[0][0] or 0)
    comment_credit = int(call_database("SELECT SUM(like) - SUM(dislike) FROM Comment WHERE user_id = ?",
                        (user_id,))[0][0] or 0)
    total_credit = comment_credit + post_credit
    cur.execute("UPDATE User SET credit = ? WHERE id = ?", (total_credit, user_id))
    conn.commit()


# Flask app starts below


# The post tables gets passed to the jinja loop in "home.html".
# This is to create HTML posts for each entry in the post table.
@app.route("/")
def home():
    parameter = []
    user_id = session.get("user_id", None)
    category = session.get("category", None)
    order = session.get("order", None)
    # Build query    
    # if user_id:
    #     final_query = """SELECT Post.*,
    #                     User.username, Graded.grade AS grade FROM POST
    #                     INNER JOIN User ON Post.user_id = User.id
    #                     LEFT JOIN Graded ON grade = Graded.grade
    #                     WHERE Graded.post_id = post.id AND Graded.user_id = ?
    #                     UNION
    #                     SELECT Post.*, User.username, NULL FROM POST
    #                     INNER JOIN User ON Post.user_id = User.id"""
    #     parameter.append(user_id)
    # else:
    final_query = """SELECT Post.*, User.username FROM Post INNER JOIN User ON Post.user_id = User.id"""
    # Check for sorting
    if category:
        sort_query = " WHERE type = ?"
        parameter.append(category)
        final_query = final_query + sort_query
    if order:
        if order == "Like":
            order_query = " ORDER BY like DESC"
        elif order == "Dislike":
            order_query = " ORDER BY dislike DESC"
        final_query = final_query + order_query
    else:
        final_query = final_query + " ORDER BY id DESC"
    # Query execution
    parameter = tuple(parameter)
    print(final_query)
    post = call_database(final_query, parameter)
    return render_template("home.html", post=post, title=default_title)


# The route creates pages dynamically.
# The id variable passed into the call database function.
# Page info is passed into HTML with jinja code
@app.route("/page/<int:id>")
def page(id):
    # Page_info needs index of 0 as the result is stored in tuple inside a list
    # if session.get("user_id", None):
    #     current_user = session.get("user_id", None)
    #     page_query = """SELECT Post.*,
    #                     User.username, Graded.grade AS grade FROM POST
    #                     INNER JOIN User ON Post.user_id = User.id
    #                     LEFT JOIN Graded ON grade = Graded.grade
    #                     WHERE Graded.post_id = post.id AND Graded.user_id = ? AND Post.id = ?
    #                     UNION
    #                     SELECT Post.*, User.username, NULL FROM POST
    #                     INNER JOIN User ON Post.user_id = User.id
    #                     WHERE Post.id = ?
    #                     """
    #     comment_query = """SELECT Comment.*,
    #                     User.username, Graded.grade AS grade FROM Comment
    #                     INNER JOIN User ON Comment.user_id = User.id
    #                     LEFT JOIN Graded ON grade = Graded.grade
    #                     WHERE Graded.comment_id = Comment.id AND Graded.user_id = ? AND Comment.comment_id IS NULL AND Comment.post_id = ?
    #                     UNION
    #                     SELECT Comment.*, User.username, NULL FROM Comment
    #                     INNER JOIN User ON Comment.user_id = User.id
    #                     WHERE Comment.comment_id IS NULL AND Comment.post_id = ?"""
    #     reply_query = """SELECT Comment.*,
    #                     User.username, Graded.grade AS grade FROM Comment
    #                     INNER JOIN User ON Comment.user_id = User.id
    #                     LEFT JOIN Graded ON grade = Graded.grade
    #                     WHERE Graded.comment_id = Comment.id AND Graded.user_id = ? AND Comment.comment_id IS NOT NULL AND Comment.post_id = ?
    #                     UNION
    #                     SELECT Comment.*, User.username, NULL FROM Comment
    #                     INNER JOIN User ON Comment.user_id = User.id
    #                     WHERE Comment.comment_id IS NOT NULL AND Comment.post_id = ?"""
    #     parameter = (current_user, id, id)
    # else:
    page_query = """SELECT Post.*, User.username FROM Post INNER JOIN User ON Post.user_id = User.id WHERE Post.id = ?"""
    comment_query = """SELECT Comment.*, User.username FROM Comment INNER JOIN User ON Comment.user_id = User.id
                    WHERE Comment.comment_id IS NULL AND Comment.post_id = ? """
    reply_query = """SELECT Comment.*, User.username FROM Comment INNER JOIN User ON Comment.user_id = User.id
                    WHERE Comment.comment_id IS NOT NULL AND Comment.post_id = ? """
    parameter = (id,)
    page_info = call_database(page_query, parameter)[0]
    comment = call_database(comment_query, parameter)
    print(comment)
    reply = call_database(reply_query, parameter)
    return render_template("page.html",
                           page=page_info,
                           comment=comment,
                           reply=reply,
                           title=page_info[1])


# Page where user replies to a comment.
@app.route("/page/reply_to/<int:post_id>/<int:comment_id>")
def reply_to(post_id, comment_id):
    reffered_comment = call_database("""SELECT * FROM Comment
                                     WHERE id = ?
                                     AND post_id = ?""",
                                     (comment_id, post_id))[0]
    return render_template("reply.html", comment=reffered_comment, title=default_title)


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
    user_post = call_database("SELECT * FROM Post WHERE user_id = ?", (id,))
    user_info = call_database("SELECT * FROM User WHERE id = ?", (id,))[0]
    return render_template("user.html", user_info=user_info, user_post=user_post, id=id, title=user_info[1])


# Gets the form values from the home page,
# The variables get updated to the database.
@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        type = request.form["type"]
        date = today()
        update_post(type, title, content, date, session["user_id"])
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
        update_comment(session["user_id"], post_id, content, date)
        return redirect(request.referrer)


# Update database with reply
@app.route("/reply", methods=["GET", "POST"])
def reply():
    if request.method == "POST":
        content = request.form["content"]
        post_id = request.form["post_id"]
        comment_id = request.form["comment_id"]
        date = today()
        update_comment(session["user_id"], post_id, content, date, comment_id)
        return redirect(url_for("page", id=post_id))


# Update post or comment with like or dislike.
@app.route("/grade/<int:id>/", methods=["GET", "POST"])
def grade(id):
    if not session.get("user_id", None ):
        return redirect(request.referrer)
    if request.method == "POST":
        user_id = session.get("user_id", None)
        table = request.form["table"]
        grade = request.form["grade"]
        # Find if user already liked or disliked post/comment
        if table == "Post":
            query = "SELECT grade FROM Graded WHERE user_id = ? AND post_id = ?"
        elif table == "Comment":
            query = "SELECT grade FROM Graded WHERE user_id = ? AND comment_id = ?"
        existing_grade = call_database(query, (user_id, id))
        # Prevent user for giving the same grade to posts/comments Otherwise give grade.
        if not existing_grade:
            graded(user_id, table, id, grade)
            update_grade(id, table)
        # Change grade by user
        elif existing_grade[0][0] != grade:
            graded(user_id, table, id, grade, True)
            update_grade(id, table)
        # Build url No section exception
        try:
            section = request.form["section"]
            url = request.referrer + f"#{str(section)}"
        except werkzeug.exceptions.BadRequestKeyError:
            url = request.referrer
        return redirect(url)
            

# Creates user account and adds to the database
# Password is salted and hashed
@app.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        date = today()
        # Get existing usernames then converts result into list without single element tuples
        existing_usernames = call_database("SELECT username FROM User")
        existing_usernames = [i[0] for i in existing_usernames]
        if username not in existing_usernames:
            create_user(username, date, (generate_password_hash(password, salt_length=16)))
            flash("Account created, log in to access your account", "info")
            return redirect(url_for("account", action="sign_in"))
        else:
            flash("That username already exists", "info")
            return redirect(request.referrer)


# Activates user session if user sucessfuly logs in
@app.route("/sign_in", methods=["GET", "POST"])
def sign_in():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user_info = call_database("""SELECT id, username, password_hash FROM User WHERE username = ?""", (username,))
        if not user_info:
            flash("Username or password is incorrect")
            return redirect(request.referrer)
        user_info = user_info[0]
        if not check_password_hash(user_info[2], password):
            flash("Username or password is incorrect")
            return redirect(request.referrer)
        else:
            session["user_id"] = user_info[0]
            credit_update(session["user_id"])
            flash(f"Logged in successfully as {username}", "info")
            return redirect(url_for("home"))       


# Filter posts
@app.route("/sort/<type>", methods=["GET", "POST"])
def sort(type):
    if request.method == "POST":
        if type == "sort":
            session["category"] = request.form["type"]
            return redirect(request.referrer)
        elif type == "order":
            session["order"] = request.form["order"]
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
        id = request.form["id"]
        type = request.form["type"]
        delete_entry(type, id)
        return redirect(request.referrer)


# Close database once app is closed.
@app.teardown_appcontext
def teardown_db(_):
    get_db().close()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port="8000")
