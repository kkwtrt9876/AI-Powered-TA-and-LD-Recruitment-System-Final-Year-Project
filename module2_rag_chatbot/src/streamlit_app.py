import streamlit as st
import time
import sys
from pathlib import Path
from dotenv import load_dotenv

st.set_page_config(
    page_title="Academic Assistant 🤖", 
    layout="wide", 
    page_icon="🎓",
    initial_sidebar_state="expanded"
)

# Enhanced CSS with Cyberpunk/Neon theme
CSS = """
<style>
:root {
    /* Light Theme Colors */
    --primary: #4a90e2;
    --primary-light: #6ba8ff;
    --primary-dark: #357abd;
    --secondary: #e0e4e8;
    --secondary-light: #ffffff;
    --accent: #4a90e2;
    --accent-light: #a3c9f5;
    --dark: #222222;
    --dark-card: #f4f6f9;
    --light: #222222;
    --gray: #555555;
    
    /* Gradients */
    --gradient-bg: #e0e4e8;
    --gradient-header: linear-gradient(135deg, #ffffff, #d1d5db);
    --gradient-user: #e3e6eb;
    --gradient-bot: #ffffff;
    --gradient-sidebar: #f4f6f9;
    --gradient-button: #4a90e2;
    --gradient-card: linear-gradient(145deg, #ffffff, #e3e6eb);
    
    /* Effects */
    --glow-primary: 0 4px 12px rgba(0, 0, 0, 0.05);
    --glow-secondary: 0 4px 12px rgba(0, 0, 0, 0.05);
    --glow-accent: 0 4px 12px rgba(0, 0, 0, 0.05);
    --shadow-lg: 0 10px 30px rgba(0, 0, 0, 0.1);
    --shadow-md: 4px 4px 12px rgba(0, 0, 0, 0.1), -4px -4px 12px rgba(255, 255, 255, 0.7);
    --shadow-sm: 0 4px 8px rgba(0, 0, 0, 0.05);
    
    /* Glass Effects */
    --glass-bg: rgba(255, 255, 255, 0.85);
    --glass-border: rgba(0, 0, 0, 0.05);
    --glass-highlight: rgba(0, 0, 0, 0.02);
}

* {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    margin: 0;
    padding: 0;
}

/* Main app background */
.stApp {
    background: var(--gradient-bg);
    background-attachment: fixed;
    min-height: 100vh;
}

/* SILVER HEADER */
[data-testid="stHeader"], .stAppHeader {
    background-color: #e5e7eb !important;
    border-bottom: 1px solid #d1d5db !important;
    backdrop-filter: blur(10px);
}


/* Animated background particles */
.stApp::before {
    display: none;
}

/* Main container style for major blocks */
.main-content-block {
    max-width: 1100px;
    margin: 2rem auto;
    padding: 2.5rem;
    background: var(--glass-bg);
    backdrop-filter: blur(20px) saturate(180%);
    border-radius: 32px;
    border: 1px solid var(--glass-border);
    box-shadow: var(--shadow-lg);
    position: relative;
    overflow: hidden;
}

/* Header with animated gradient */
.header-container {
    background: var(--gradient-card);
    padding: 2.5rem;
    border-radius: 24px;
    margin-bottom: 2.5rem;
    text-align: center;
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(0, 255, 157, 0.1);
    box-shadow: var(--shadow-md);
}

.header-container::after {
    display: none;
}

.header-title {
    font-size: 3rem;
    font-weight: 900;
    margin-bottom: 0.8rem;
    color: var(--dark) !important;
    letter-spacing: -0.5px;
}

.header-subtitle {
    font-size: 1.2rem;
    color: var(--dark) !important;
    opacity: 0.9;
    font-weight: 300;
    max-width: 600px;
    margin: 0 auto;
    line-height: 1.6;
}

/* Status indicator with glow */
.status-container {
    display: flex;
    gap: 1.5rem;
    margin-bottom: 2rem;
    flex-wrap: wrap;
}

.status-card {
    flex: 1;
    min-width: 200px;
    background: #ffffff;
    padding: 1.2rem 1.5rem;
    border-radius: 20px;
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow-sm);
    transition: all 0.3s ease;
}

.status-card:hover {
    transform: translateY(-5px);
    box-shadow: var(--glow-primary), var(--shadow-md);
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 12px;
}

.status-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    position: relative;
}

.status-dot.online {
    background: var(--primary);
    box-shadow: 0 0 10px var(--primary);
}

.status-dot.offline {
    background: #ff4757;
    box-shadow: 0 0 15px #ff4757;
}

.status-text {
    color: var(--dark) !important;
    font-weight: 600;
    font-size: 1.1rem;
}

.status-description {
    color: var(--gray) !important;
    font-size: 0.9rem;
    margin-top: 8px;
}

/* Badges */
.badge-container {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 1rem;
}

.badge {
    padding: 8px 16px;
    background: #ffffff;
    border: 1px solid var(--border-color);
    border-radius: 20px;
    color: var(--primary);
    font-size: 0.9rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.3s ease;
}

.badge:hover {
    background: var(--secondary);
    transform: translateY(-2px);
    box-shadow: var(--shadow-sm);
}

/* Chat container with scroll glow */
.chat-container {
    background: #ffffff;
    backdrop-filter: blur(10px);
    border-radius: 24px;
    padding: 1.5rem;
    max-height: 60vh;
    overflow-y: auto;
    margin-bottom: 1.5rem;
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow-md);
    position: relative;
}

.chat-container::-webkit-scrollbar {
    width: 10px;
}

.chat-container::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 10px;
}

.chat-container::-webkit-scrollbar-thumb {
    background: var(--gradient-user);
    border-radius: 10px;
    border: 2px solid transparent;
    background-clip: padding-box;
}

/* Chat messages with glow effects */
.chat-message {
    display: flex;
    align-items: flex-start;
    gap: 15px;
    margin-bottom: 1.5rem;
    animation: messageSlide 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.chat-message.user {
    flex-direction: row-reverse;
}

.avatar {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    font-weight: bold;
    flex-shrink: 0;
    position: relative;
    z-index: 1;
}

.avatar::before {
    content: '';
    position: absolute;
    top: -2px;
    left: -2px;
    right: -2px;
    bottom: -2px;
    border-radius: 50%;
    z-index: -1;
    animation: avatarGlow 2s infinite;
}

.user .avatar {
    background: var(--gradient-user);
    color: var(--dark);
}

.user .avatar::before {
    background: var(--gradient-user);
    filter: blur(8px);
    opacity: 0.6;
}

.bot .avatar {
    background: var(--gradient-bot);
    color: var(--dark);
}

.bot .avatar::before {
    display: none;
}

.message-bubble {
    max-width: 70%;
    padding: 1.5rem 1.8rem; /* Increased top padding */
    border-radius: 24px;
    position: relative;
    line-height: 1.6;
    word-wrap: break-word;
    box-shadow: var(--shadow-sm);
    backdrop-filter: blur(10px);
    border: 1px solid transparent;
    background-clip: padding-box;
    position: relative;
    margin-top: 10px; /* Drag down slightly from the top */
}

.message-bubble::before {
    content: '';
    position: absolute;
    top: -1px;
    left: -1px;
    right: -1px;
    bottom: -1px;
    border-radius: 25px;
    z-index: -1;
}

.user .message-bubble {
    background: #e3e6eb;
    border-color: var(--border-color);
    color: var(--dark) !important;
    border-bottom-right-radius: 8px;
}

.user .message-bubble::before {
    display: none;
}

.bot .message-bubble {
    background: #ffffff;
    border-color: var(--border-color);
    color: var(--dark) !important;
    border-bottom-left-radius: 8px;
}

.bot .message-bubble::before {
    display: none;
}

.message-time {
    font-size: 0.8rem;
    opacity: 0.7;
    margin-top: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--gray);
}

/* Input area */
.input-container {
    background: #ffffff;
    backdrop-filter: blur(20px);
    padding: 2rem;
    border-radius: 24px;
    margin-top: 2rem;
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow-md);
    transition: all 0.3s ease;
    position: relative;
}

.input-container:focus-within {
    border-color: var(--primary);
    box-shadow: var(--glow-primary), var(--shadow-lg);
    transform: translateY(-2px);
}

.input-container::before {
    display: none;
}

.stTextArea textarea {
    border-radius: 18px !important;
    border: 2px solid var(--border-color) !important;
    padding: 1.2rem !important;
    font-size: 1.05rem !important;
    background: #ffffff !important;
    color: var(--dark) !important;
    transition: all 0.3s ease !important;
    line-height: 1.5 !important;
    backdrop-filter: blur(10px);
}

.stTextArea div[data-baseweb="textarea"],
.stTextArea div[data-baseweb="base-input"] {
    background-color: #ffffff !important;
    border-radius: 18px !important;
}

.stTextArea textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(74, 144, 226, 0.1) !important;
    outline: none !important;
    background: #ffffff !important;
}

.stTextArea textarea::placeholder {
    color: var(--gray) !important;
}

/* Send button */
.send-button {
    background: var(--gradient-button) !important;
    color: var(--dark) !important;
    border: none !important;
    padding: 1rem 2.5rem !important;
    border-radius: 18px !important;
    font-weight: 800 !important;
    font-size: 1.1rem !important;
    transition: all 0.3s ease !important;
    width: 100%;
    margin-top: 1.2rem;
    letter-spacing: 1px;
    text-transform: uppercase;
    box-shadow: var(--glow-primary) !important;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(10px);
}

.send-button::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.2),
        transparent
    );
    transition: 0.5s;
}

.send-button:hover::before {
    left: 100%;
}

.send-button:hover {
    transform: translateY(-3px) scale(1.02) !important;
    box-shadow: 
        0 4px 12px rgba(74, 144, 226, 0.3),
        0 8px 24px rgba(0, 0, 0, 0.1) !important;
}

.send-button:active {
    transform: translateY(-1px) scale(0.98) !important;
}

.keyboard-hint {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.9rem;
    color: var(--gray);
    margin-top: 1rem;
    padding: 10px 16px;
    background: #f9f9fb;
    border-radius: 12px;
    border: 1px solid var(--border-color);
}

.keyboard-key {
    background: #ffffff;
    color: var(--primary);
    padding: 4px 12px;
    border-radius: 8px;
    font-family: 'Courier New', monospace;
    font-weight: bold;
    font-size: 0.9rem;
    border: 1px solid var(--border-color);
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--gradient-sidebar) !important;
    border-right: 1px solid var(--border-color);
}

.sidebar-content {
    padding: 2rem 1rem;
}

.sidebar-title {
    color: var(--primary);
    font-size: 1.8rem;
    font-weight: 800;
    margin-bottom: 2rem;
    text-align: center;
    text-shadow: none;
}

/* Animations */
@keyframes pulseBackground {
    0% { opacity: 0.3; }
    100% { opacity: 0.7; }
}

@keyframes containerFloat {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

@keyframes neonBorder {
    0% { filter: blur(15px) hue-rotate(0deg); }
    100% { filter: blur(15px) hue-rotate(360deg); }
}

@keyframes shimmer {
    0% { background-position: -200% -200%; }
    100% { background-position: 200% 200%; }
}

@keyframes pulseGlow {
    0%, 100% { 
        box-shadow: 0 0 15px var(--primary);
        transform: scale(1);
    }
    50% { 
        box-shadow: 0 0 30px var(--primary);
        transform: scale(1.1);
    }
}

@keyframes messageSlide {
    from { 
        opacity: 0;
        transform: translateX(-30px) scale(0.9);
    }
    to { 
        opacity: 1;
        transform: translateX(0) scale(1);
    }
}

@keyframes avatarGlow {
    0%, 100% { 
        opacity: 0.6;
        transform: scale(1);
    }
    50% { 
        opacity: 0.8;
        transform: scale(1.05);
    }
}

/* Typing indicator */
.typing-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 1.2rem 1.5rem;
    background: #ffffff;
    border-radius: 20px;
    width: fit-content;
    border: 1px solid var(--border-color);
    backdrop-filter: blur(10px);
}

.typing-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 10px var(--accent);
    animation: typingBounce 1.4s infinite;
}

.typing-dot:nth-child(2) { 
    animation-delay: 0.2s; 
    background: var(--primary);
    box-shadow: 0 0 10px var(--primary);
}

.typing-dot:nth-child(3) { 
    animation-delay: 0.4s; 
    background: var(--secondary);
    box-shadow: 0 0 10px var(--secondary);
}

@keyframes typingBounce {
    0%, 60%, 100% { 
        transform: translateY(0) scale(1);
    }
    30% { 
        transform: translateY(-15px) scale(1.2);
    }
}

/* Footer */
.footer {
    text-align: center;
    padding: 2rem;
    margin-top: 2rem;
    color: var(--gray);
    font-size: 0.9rem;
    position: relative;
}

.footer::before {
    content: '';
    position: absolute;
    top: 0;
    left: 25%;
    right: 25%;
    height: 1px;
    background: linear-gradient(90deg, 
        transparent, 
        var(--primary), 
        transparent
    );
}

.footer-gradient {
    color: var(--primary);
    background: transparent;
    -webkit-text-fill-color: initial;
    font-weight: 800;
    font-size: 1.1rem;
}

/* Fix for black code blocks */
pre, code, .stMarkdown code {
    background-color: #ffffff !important;
    color: var(--dark) !important;
    border: 1px solid var(--border-color) !important;
}

/* Global text contrast fix */
.stMarkdown p, .stMarkdown span, li, .stCaption {
    color: var(--dark) !important;
}

/* Sidebar context fixes */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] span {
    color: var(--dark) !important;
}

/* Responsive design */
@media (max-width: 768px) {
    .main-container {
        margin: 1rem;
        padding: 1.5rem;
    }
    
    .header-title {
        font-size: 2rem;
    }
    
    .message-bubble {
        max-width: 85%;
    }
    
    .status-container {
        flex-direction: column;
    }
}

/* SILVER THEME REFINEMENTS */
[data-testid="stBaseButton-secondary"] {
    background-color: #d1d5db !important;
    color: #222222 !important;
    border: 1px solid #9ca3af !important;
    border-radius: 12px !important;
    box-shadow: none !important;
    transition: none !important;
}

[data-testid="stBaseButton-secondary"]:hover {
    background-color: #d1d5db !important;
    color: #222222 !important;
    transform: none !important;
    box-shadow: none !important;
    border-color: #9ca3af !important;
}

[data-testid="stBaseButton-secondary"] p {
    color: #222222 !important;
}

/* Toolbar silver theme */
[data-testid="stToolbar"] {
    background-color: #e5e7eb !important;
    border-radius: 20px !important;
    border: 1px solid #d1d5db !important;
    right: 20px !important;
    top: 10px !important;
}

/* Header buttons (Deploy, MainMenu) silver theme */
[data-testid="stBaseButton-header"],
[data-testid="stBaseButton-headerNoPadding"] {
    background-color: #d1d5db !important;
    color: #222222 !important;
    border: 1px solid #9ca3af !important;
    border-radius: 12px !important;
    margin: 0 4px !important;
    transition: none !important;
}

[data-testid="stBaseButton-header"] span,
[data-testid="stBaseButton-headerNoPadding"] span {
    color: #222222 !important;
}

[data-testid="stBaseButton-header"]:hover,
[data-testid="stBaseButton-headerNoPadding"]:hover {
    background-color: #d1d5db !important;
    transform: none !important;
    box-shadow: none !important;
}

[data-testid="stToolbar"] svg {
    fill: #222222 !important;
}

[data-testid="stToolbar"] button:hover {
    background-color: #d1d5db !important;
}

/* NUCLEAR EXPANDER FIX: Forcing white background and dark text on ALL internal states */
.stExpander, 
.stExpander *,
[data-testid="stExpanderHeader"],
[data-testid="stExpanderDetails"],
div[role="region"][aria-labelledby] {
    background-color: #ffffff !important;
    background: #ffffff !important;
    color: #222222 !important;
}

[data-testid="stExpanderHeader"] p {
    color: #222222 !important;
    font-weight: 700 !important;
    font-size: 1.1rem !important;
}

.stExpander {
    border: 1px solid var(--border-color) !important;
    border-radius: 16px !important;
    margin: 1rem 0 !important;
}

/* Ensure no shadows or glows from neon are left here */
[data-testid="stExpanderHeader"]:hover {
    background-color: #f9f9fb !important;
}



</style>

<!-- JavaScript for Ctrl+Enter and other interactions -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    // Ctrl+Enter functionality
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        textarea.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                
                // Find and click send button
                const sendButton = Array.from(document.querySelectorAll('button'))
                    .find(btn => btn.textContent.includes('Send') || btn.textContent.includes('🚀'));
                
                if (sendButton) {
                    sendButton.click();
                    showToast('🚀 Message sent!', 'success');
                }
            }
        });
    });
    
    // Auto-scroll to bottom of chat
    function scrollToBottom() {
        const chatContainer = document.querySelector('.chat-container');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    }
    
    // Scroll when new messages might be added
    const observer = new MutationObserver(scrollToBottom);
    const chatContainer = document.querySelector('.chat-container');
    if (chatContainer) {
        observer.observe(chatContainer, { childList: true, subtree: true });
    }
    
    // Initial scroll
    setTimeout(scrollToBottom, 500);
    
    // Add keyboard shortcut hint
    const textareaContainers = document.querySelectorAll('.stTextArea');
    textareaContainers.forEach(container => {
        if (!container.querySelector('.keyboard-hint')) {
            const hint = document.createElement('div');
            hint.className = 'keyboard-hint';
            hint.innerHTML = `
                <span>💡</span>
                <span>Press <span class="keyboard-key">Ctrl</span> + <span class="keyboard-key">Enter</span> to send</span>
            `;
            container.appendChild(hint);
        }
    });
    
    // Toast notification function
    function showToast(message, type = 'info') {
        // Remove existing toast
        const existingToast = document.querySelector('.custom-toast');
        if (existingToast) existingToast.remove();
        
        // Create toast
        const toast = document.createElement('div');
        toast.className = 'custom-toast';
        toast.innerHTML = `
            <div style="
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: var(--primary);
                color: #ffffff;
                padding: 1rem 1.5rem;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                z-index: 10000;
                display: flex;
                align-items: center;
                gap: 12px;
                font-weight: 600;
                animation: slideInRight 0.3s ease-out;
            ">
                <span style="font-size: 1.2rem;">✅</span>
                <span>${message}</span>
            </div>
        `;
        document.body.appendChild(toast);
        
        // Remove after 3 seconds
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    // Add slide out animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
});
</script>
"""

def load_answer_fn():
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    load_dotenv(ROOT / ".env")

    try:
        from src.rag import answer_question
        return answer_question, True, None
    except Exception as e:
        import traceback
        tb = traceback.format_exc()

        def fallback(question: str, k: int = 5) -> str:
            return (
                "✨ **OFFLINE RESPONSE MODE** ✨\n\n"
                f"**Query detected:** {question}\n\n"
                "📡 **Status:** *Running in offline simulation mode*\n"
                "⚡ **Capabilities:** Limited to demo responses\n\n"
                "🔧 **To activate full AI mode:**\n"
                "1. Configure GROQ_API_KEY in `.env`\n"
                "2. Initialize vector database\n"
                "3. Enable processing pipeline\n\n"
                "💡 **Demo response:** Based on academic recruitment protocols,\n"
                "I'd provide detailed analysis of TA/LD procedures, policy guidelines,\n"
                "and optimization strategies for your specific query."
            )
        return fallback, False, tb

answer_fn, llm_available, import_error = load_answer_fn()

# Apply CSS and JavaScript
st.markdown(CSS, unsafe_allow_html=True)


# Header
st.markdown("""
<div class="header-container">
    <div class="header-title">TA–LD Intelligent Assistant</div>
    <div class="header-subtitle">
        Hello — I'm the academic assistant. Ask me about the TA/LD recruitment system.
    </div>
</div>
""", unsafe_allow_html=True)

# Status and info cards
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
    <div class="status-card">
        <div class="status-indicator">
            <div class="status-dot {'online' if llm_available else 'offline'}"></div>
            <span class="status-text">{'TA-LD AI Assistant' if llm_available else 'SIMULATION MODE'}</span>
        </div>
        <div class="status-description">
            { 'Advanced TA-LD Engine Online' if llm_available else 'Running on demo data' }
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="status-card">
        <div class="status-indicator">
            <div class="status-dot" style="background: var(--accent);"></div>
            <span class="status-text">TA-LD Coordination Assistant</span>
        </div>
        <div class="status-description">
            Efficient access to TA & LD information and documentation
        </div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="status-card">
        <div class="status-indicator">
            <div class="status-dot" style="background: var(--primary-light);"></div>
            <span class="status-text">TA & LD Academic Assistant</span>
        </div>
        <div class="status-description">
            Your gateway to intelligent TA & LD management
        </div>
    </div>
    """, unsafe_allow_html=True)

# Badges
st.markdown("""
<div class="badge-container">
    <div class="badge">
        <span>⚡</span> <span>High-Speed Processing</span>
    </div>
    <div class="badge">
        <span>🤖</span> <span>Automated TA Allocationd</span>
    </div>
    <div class="badge">
        <span>🔍</span> <span>Instant Info Retrieval</span>
    </div>
    <div class="badge">
        <span>📊</span> <span>AI-Powered Queries</span>
    </div>
</div>
""", unsafe_allow_html=True)

if not llm_available:
    st.markdown("""
    <div style="
        background: #fef0f0;
        border: 1px solid #fcdada;
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        color: #ef4444;
        text-align: center;
        backdrop-filter: blur(10px);
    ">
        <div style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.5rem;">
            ⚠️ OFFLINE MODE ACTIVE
        </div>
        <div style="font-size: 0.95rem; opacity: 0.9;">
            Running in simulation. For full AI access, configure API keys.
        </div>
    </div>
    """, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("""
    <div class="sidebar-content">
        <div class="sidebar-title">TA LD ASSISTANT</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    k = st.slider(
        "**CONTEXT DEPTH**",
        min_value=1,
        max_value=10,
        value=5,
        help="Adjust how many document chunks to analyze for context"
    )
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear Chat", use_container_width=True, type="secondary"):
            st.session_state.clear()
            st.rerun()
    
    
    st.markdown("---")
    
    
    
    with st.expander("ℹ️ SYSTEM INFO", expanded=False):
        st.markdown("""
        **TA–LD Intelligent Assistant**
        
        **Capabilities:**
        - 🔍 TA Application Guidance
        - 🧠 LD Eligibility Info 
        - 📚 TA Compensation Details
        - ⚡ Real-Time Academic Answers
        
        
        """)
# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "bot",
            "content": """
            ### 🎓 **TA–LD Academic Assistant**
            
            **Welcome!** I am here to help you navigate the TA & LD recruitment and allocation process.
            
            **Available Information:**
            • TA Allocation & Scheduling
            • LD Selection criteria  
            • Academic Workflow Guidelines
            
            **You can ask me things like:**
            - "How can I apply for a TA position?"
            - "What are the eligibility criteria for an LD position?"
            - "What is the payment structure for TAs?"
            
            ---
            💡 **Tip:** Press **Ctrl + Enter** for a quick send!
            """,
            "timestamp": time.strftime("%H:%M")
        }
    ]

# Chat display
chat_container = st.container()
with chat_container:

    
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="chat-message user">
                <div class="message-bubble">
                    <div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 8px; color: var(--primary);">
                        USER QUERY
                    </div>
                    {msg["content"]}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-message bot">
                <div class="message-bubble">
                    <div style="font-size: 1rem; font-weight: 700; margin-bottom: 8px; color: var(--primary);">
                        TA–LD Assistant
                    </div>
                    {msg["content"]}
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    
    st.caption(f"Last updated: {time.strftime('%H:%M:%S')}")




# Input area
with st.container():


    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_area(
            "💬 **YOUR ACADEMIC QUERY**",
            placeholder="Enter your academic query here... (Press Ctrl+Enter for instant transmission)",
            height=120,
            label_visibility="collapsed",
            key="user_input"
        )
        
        submit_button = st.form_submit_button(
            label="🚀 SEND QUERY",
            type="primary",
            use_container_width=True
        )


    # Handle form submission
    if submit_button and user_input.strip():
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": time.strftime("%H:%M")
        })
        
        # Show typing indicator
        with st.spinner(""):
            typing_placeholder = st.empty()
            typing_placeholder.markdown("""
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <span style="margin-left: 12px; color: var(--accent); font-weight: 600;">
                    PROCESSING QUERY...
                </span>
            </div>
            """, unsafe_allow_html=True)
            
            try:
                # Get response
                reply = answer_fn(user_input, k=k)
            except Exception as e:
                reply = f"""
                ⚡ **PROCESSING INTERRUPTED**
                
                **Error Code:** ERR-{hash(str(e)) % 10000:04d}
                **Issue:** {str(e)}
                
                **Recovery Protocol:**
                1. AI connection recalibration required
                2. API endpoint verification needed
                3. Vector database connectivity check
                
                **Temporary Solution:**
                Please rephrase your query or try again in 30 seconds.
                """
            
            # Remove typing indicator
            typing_placeholder.empty()
        
        # Add bot response
        st.session_state.messages.append({
            "role": "bot",
            "content": reply,
            "timestamp": time.strftime("%H:%M")
        })
        
        # Rerun to update the chat display
        st.rerun()






# Footer
st.markdown("""
<div class="footer">
    <p>
        <span class="footer-gradient">TA–LD Intelligent Assistant</span>
        <br>
        <span style="font-size: 0.8rem;">TA–LD Intelligent Assistant</span>
    </p>
    <p style="font-size: 0.8rem; opacity: 0.6; margin-top: 0.5rem;">
        🔮 TA-LD Assistant • ⚡ Real-time academic updates • 🛡️ Security Enforced
    </p>
</div>
""", unsafe_allow_html=True)