import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from ytmusicapi import YTMusic

# Database setup
DB_URL = "postgresql://vofodb_user:Y7MQfAWwEtsiHQLiGHFV7ikOI2ruTv3u@dpg-d5lm4ongi27c7390kq40-a/vofodb"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Use a different hashing scheme
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)

class LikedSong(Base):
    __tablename__ = "liked_songs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    song_id = Column(String)
    title = Column(String)
    artist = Column(String)
    thumbnail = Column(String)

Base.metadata.create_all(bind=engine)

app = FastAPI()
yt = YTMusic()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try: 
        yield db
    finally: 
        db.close()

@app.post("/api/register")
def register(data: dict, db: Session = Depends(get_db)):
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        raise HTTPException(400, "Need username and password")
    
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(400, "Username taken")
    
    hashed = pwd_context.hash(password)
    user = User(username=username, password=hashed)
    db.add(user)
    db.commit()
    return {"success": True, "user_id": user.id, "username": user.username}

@app.post("/api/login")
def login(data: dict, db: Session = Depends(get_db)):
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.password):
        raise HTTPException(401, "Bad login")
    
    return {"success": True, "user_id": user.id, "username": user.username}

@app.post("/api/like")
def toggle_like(data: dict, db: Session = Depends(get_db)):
    existing = db.query(LikedSong).filter(
        LikedSong.user_id == data['user_id'], 
        LikedSong.song_id == data['song_id']
    ).first()
    
    if existing:
        db.delete(existing)
        db.commit()
        return {"status": "unliked"}
    
    new_like = LikedSong(
        user_id=data['user_id'], 
        song_id=data['song_id'], 
        title=data['title'], 
        artist=data['artist'], 
        thumbnail=data['thumbnail']
    )
    db.add(new_like)
    db.commit()
    return {"status": "liked"}

@app.get("/api/liked/{user_id}")
def get_liked(user_id: int, db: Session = Depends(get_db)):
    likes = db.query(LikedSong).filter(LikedSong.user_id == user_id).all()
    return [{"id": l.song_id, "title": l.title, "artist": l.artist, "thumbnail": l.thumbnail} for l in likes]

@app.get("/api/trending")
def trending():
    try:
        songs = yt.get_charts(country="IN")['songs']['items']
        return [{"id": s['videoId'], "title": s['title'], "artist": s['artists'][0]['name'], "thumbnail": s['thumbnails'][-1]['url']} for s in songs[:15]]
    except: 
        return []

@app.get("/api/search")
def search(q: str):
    try:
        results = yt.search(q, filter="songs")
        return [{"id": r['videoId'], "title": r['title'], "artist": r['artists'][0]['name'], "thumbnail": r['thumbnails'][-1]['url']} for r in results]
    except: 
        return []

@app.get("/")
def home():
    try:
        with open("index.html", "r", encoding="utf-8") as f: 
            return HTMLResponse(f.read())
    except:
        return HTMLResponse("<h1>NEWoNE Music</h1><p>Frontend loading...</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
