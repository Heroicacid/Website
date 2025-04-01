from datetime import date
from typing import List
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
import smtplib


MAIL = "sandarbaz55@gmail.com"
PASS = "vwwk royr lwqp vbmd"


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
app.config['CKEDITOR_PKG_TYPE'] = 'standard'
ckeditor = CKEditor(app)
Bootstrap5(app)



#INITIALIZE GRAVATAR
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


#CREATING DECORATOR FOR ADMIN_ONLY USAGES
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #get_id returns a str
        if current_user.get_id() == "1" :
            return f(*args, **kwargs)
        else:
            return abort(403)
    return decorated_function


#FLASK LOGIN
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)



#USER TABLE (PARENT)
class User(db.Model, UserMixin):
    id: Mapped[int] = mapped_column(Integer, primary_key= True)
    email: Mapped[str] = mapped_column(String(250), unique= True)
    password: Mapped[str] = mapped_column(String(250))
    name: Mapped[str] = mapped_column(String(250))

    #PARENT RELATIONSHIPS
    #to BlogPost
    posts: Mapped[List["BlogPost"]] = relationship(back_populates="author")

    #To Comment
    comments: Mapped[List["Comment"]] = relationship(back_populates= "commenter")



# BLOGS TABLE (CHILD)
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    #CHILD RELATIONSHIPS
    #to User
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    #this is the attr that gets related to the parent table
    author: Mapped["User"] = relationship(back_populates="posts")

    #PARENT RELATIONSHIPS
    #list of comments
    comment: Mapped[List["Comment"]] = relationship(back_populates="parent_post")


#COMMENTS TABLE
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key= True)
    text: Mapped[str] = mapped_column(Text(1000), nullable = False)

    #CHILD RELATIONSHIPS
    #to User
    commenter_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    commenter: Mapped[List["User"]] = relationship(back_populates="comments")

    #to BlogPost
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("blog_posts.id"))
    parent_post: Mapped["BlogPost"] = relationship(back_populates= "comment")



with app.app_context():
    db.create_all()


@app.route('/register', methods = ["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if user:
            flash("This E-mail already exists. try another one!")
            redirect(url_for("register"))
        else:
            new_user = User(
                email = form.email.data,
                password = generate_password_hash(form.password.data, method= "pbkdf2:sha256", salt_length= 8),
                name = form.name.data
            )
            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)
            return redirect(url_for("get_all_posts", logged_in = True))

    return render_template("register.html", form = form)


@app.route('/login', methods = ["POST", "GET"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        password = login_form.password.data
        result = db.session.execute(db.select(User).where(User.email == login_form.email.data))
        user = result.scalar()
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_posts', logged_in = True))

    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, current_user = current_user)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You are not logged in yet.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text = comment_form.comment.data,
            parent_post = requested_post,
            commenter = current_user
        )
        db.session.add(new_comment)
        db.session.commit()

    return render_template("post.html", post=requested_post, form = comment_form)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods= ["GET", "POST"])
def contact():
    if request.method == "POST":
        with smtplib.SMTP("smtp.gmail.com", 587 ) as connection:
            connection.connect("smtp.gmail.com")
            connection.starttls()
            connection.login(MAIL, PASS)
            connection.sendmail(
            from_addr= MAIL, 
            to_addrs= MAIL, 
            msg= f"Subject: New Message!\n\nName: {request.form['name']}\nPhone: {request.form["phone"]}\nMessage:\n{request.form["message"]}"
            )
            return render_template("contact.html", msg_sent = True)
    return render_template("contact.html", msg_sent = False)


if __name__ == "__main__":
    app.run(debug=True, port=5002)
