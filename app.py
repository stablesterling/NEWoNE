import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from ytmusicapi import YTMusic

# --- DATABASE SETUP ---
DB_URL = "postgresql://vofodb_user:Y7MQfAWwEtsiHQLiGHFV7ikOI2ruTv3u@dpg-d5lm4ongi27c7390kq40-a/vofodb"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FIX: Use pbkdf2_sha256 instead of bcrypt to avoid password length limit
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"], 
    deprecated="auto"
)

# --- MODELS ---
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

# Dependency
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- AUTH ROUTES ---
@app.post("/api/register")
async def register(data: dict, db: Session = Depends(get_db)):
    try:
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        # Validate inputs
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password are required")
        
        if len(username) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
        
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
        # Hash the password
        hashed_pwd = pwd_context.hash(password)
        
        # Create user
        user = User(username=username, password=hashed_pwd)
        
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return {
            "success": True, 
            "message": "Account created successfully",
            "user_id": user.id,
            "username": user.username
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/login")
async def login(data: dict, db: Session = Depends(get_db)):
    try:
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password are required")
        
        # Find user
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password
        if not pwd_context.verify(password, user.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return {
            "success": True, 
            "user_id": user.id, 
            "username": user.username
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# --- LIKES ROUTES ---
@app.post("/api/like")
async def toggle_like(data: dict, db: Session = Depends(get_db)):
    try:
        user_id = data.get('user_id')
        song_id = data.get('song_id')
        
        if not user_id or not song_id:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Check if song already liked
        existing = db.query(LikedSong).filter(
            LikedSong.user_id == user_id, 
            LikedSong.song_id == song_id
        ).first()
        
        if existing:
            db.delete(existing)
            db.commit()
            return {"status": "unliked"}
        
        # Add new like
        new_like = LikedSong(
            user_id=user_id, 
            song_id=song_id, 
            title=data.get('title', ''), 
            artist=data.get('artist', ''), 
            thumbnail=data.get('thumbnail', '')
        )
        db.add(new_like)
        db.commit()
        return {"status": "liked"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to toggle like: {str(e)}")

@app.get("/api/liked/{user_id}")
async def get_liked(user_id: int, db: Session = Depends(get_db)):
    try:
        likes = db.query(LikedSong).filter(LikedSong.user_id == user_id).all()
        return [{
            "id": l.song_id, 
            "title": l.title, 
            "artist": l.artist, 
            "thumbnail": l.thumbnail
        } for l in likes]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch liked songs: {str(e)}")

# --- MUSIC ROUTES ---
@app.get("/api/trending")
async def trending():
    try:
        charts = yt.get_charts(country="IN")
        songs = charts.get('songs', {}).get('items', [])
        return [{
            "id": s.get('videoId', ''),
            "title": s.get('title', 'Unknown'),
            "artist": s.get('artists', [{}])[0].get('name', 'Unknown'),
            "thumbnail": s.get('thumbnails', [{}])[-1].get('url', '')
        } for s in songs[:15]]
    except Exception as e:
        print(f"Error fetching trending: {e}")
        return []

@app.get("/api/search")
async def search(q: str):
    try:
        if not q or len(q.strip()) < 1:
            return []
        
        results = yt.search(q.strip(), filter="songs")
        return [{
            "id": r.get('videoId', ''),
            "title": r.get('title', 'Unknown'),
            "artist": r.get('artists', [{}])[0].get('name', 'Unknown'),
            "thumbnail": r.get('thumbnails', [{}])[-1].get('url', '')
        } for r in results if r.get('videoId')]
    except Exception as e:
        print(f"Error searching: {e}")
        return []

@app.get("/", response_class=HTMLResponse)
def home():
    try:
        with open("index.html", "r", encoding="utf-8") as f: 
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>Music App</h1><p>index.html not found</p>")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "vofo-music-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
