import { useState, useEffect } from "react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// ---------- Validation Helpers ----------
const validateEmailSyntax = (email) => {
  const pattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  return pattern.test(email);
};

const validateMobileSyntax = (mobile) => {
  const pattern = /^\d{10}$/;
  return pattern.test(mobile);
};

const validatePasswordStrength = (password) => {
  if (password.length < 6) return "Password must be at least 6 characters";
  return null;
};

// Rainbow colors for first letter
const getLetterColor = (letter) => {
  const colors = {
    A: "#ef4444", B: "#f97316", C: "#f59e0b", D: "#eab308", E: "#84cc16",
    F: "#22c55e", G: "#10b981", H: "#14b8a6", I: "#06b6d4", J: "#0ea5e9",
    K: "#3b82f6", L: "#6366f1", M: "#8b5cf6", N: "#a855f7", O: "#d946ef",
    P: "#ec4899", Q: "#f43f5e", R: "#fb7185", S: "#facc15", T: "#4ade80",
    U: "#2dd4bf", V: "#60a5fa", W: "#c084fc", X: "#f472b6", Y: "#fde047",
    Z: "#34d399"
  };
  return colors[letter.toUpperCase()] || "#7c3aed";
};

// Convert topic to Camel Case (first letter capital, rest small)
const toCamelCase = (str) => {
  if (!str) return "Notes";
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
};

export default function App() {
  // ---------- Auth State ----------
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [user, setUser] = useState(JSON.parse(localStorage.getItem("user")));
  const [authView, setAuthView] = useState("login");
  const [form, setForm] = useState({
    name: "",
    email: "",
    mobile: "",
    password: "",
    confirm_password: "",
  });
  const [errors, setErrors] = useState({
    name: "",
    email: "",
    mobile: "",
    password: "",
    confirm: "",
    general: "",
  });

  // ---------- Main App State ----------
  const [loading, setLoading] = useState(false);
  const [sidebar, setSidebar] = useState(false);
  const [topic, setTopic] = useState("");
  const [answer, setAnswer] = useState("");
  const [quiz, setQuiz] = useState([]);
  const [flashcards, setFlashcards] = useState([]);
  const [flippedIndex, setFlippedIndex] = useState(null);
  const [history, setHistory] = useState([]);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizFeedback, setQuizFeedback] = useState({});
  const [quizScore, setQuizScore] = useState(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  // ---------- Helper Functions ----------
  const getUserID = () => {
    if (!user?.name) return "";
    const namePart = user.name.replace(/\s/g, "").slice(0, 6);
    const randomNum = Math.floor(1000 + Math.random() * 9000);
    return `${namePart}${randomNum}`;
  };

  const formatType = (type) => {
    if (type === "explain") return "Explain";
    if (type === "quiz") return "Quiz";
    if (type === "flashcards") return "Flashcard";
    return type;
  };

  // ---------- History ----------
  useEffect(() => {
    if (token) fetchHistory();
  }, [token]);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API}/history`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok) setHistory(data);
    } catch (err) {
      console.error("History fetch failed");
    }
  };

  const deleteHistoryItem = async (id) => {
    try {
      const res = await fetch(`${API}/history/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) fetchHistory();
    } catch (err) {
      console.error("Delete failed");
    }
  };

  const clearAllHistory = async () => {
    try {
      const res = await fetch(`${API}/history/clear/all`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchHistory();
        setShowClearConfirm(false);
      }
    } catch (err) {
      console.error("Clear all failed");
    }
  };

  // ---------- Inline Validation ----------
  const validateSignup = () => {
    let isValid = true;
    const newErrors = { name: "", email: "", mobile: "", password: "", confirm: "", general: "" };
    
    if (!form.name.trim()) {
      newErrors.name = "This field is required";
      isValid = false;
    }
    if (!form.email.trim()) {
      newErrors.email = "This field is required";
      isValid = false;
    } else if (!validateEmailSyntax(form.email)) {
      newErrors.email = "Enter a valid email address (e.g., name@example.com)";
      isValid = false;
    }
    if (!form.mobile.trim()) {
      newErrors.mobile = "This field is required";
      isValid = false;
    } else if (!validateMobileSyntax(form.mobile)) {
      newErrors.mobile = "Enter a valid 10-digit mobile number";
      isValid = false;
    }
    if (!form.password.trim()) {
      newErrors.password = "This field is required";
      isValid = false;
    } else {
      const pwdErr = validatePasswordStrength(form.password);
      if (pwdErr) {
        newErrors.password = pwdErr;
        isValid = false;
      }
    }
    if (!form.confirm_password.trim()) {
      newErrors.confirm = "This field is required";
      isValid = false;
    } else if (form.password !== form.confirm_password) {
      newErrors.confirm = "Passwords do not match";
      isValid = false;
    }
    
    setErrors(newErrors);
    return isValid;
  };

  const validateLogin = () => {
    let isValid = true;
    const newErrors = { email: "", password: "", general: "" };
    if (!form.email.trim()) {
      newErrors.email = "This field is required";
      isValid = false;
    }
    if (!form.password.trim()) {
      newErrors.password = "This field is required";
      isValid = false;
    }
    setErrors(newErrors);
    return isValid;
  };

  // ---------- Auth Submit ----------
  const handleAuth = async (e) => {
    e.preventDefault();
    setErrors({ ...errors, general: "" });

    if (authView === "signup") {
      if (!validateSignup()) return;
    } else {
      if (!validateLogin()) return;
    }

    const endpoint = authView === "login" ? "login" : "signup";
    const payload =
      authView === "login"
        ? { identifier: form.email.trim(), password: form.password.trim() }
        : {
            name: form.name.trim(),
            email: form.email.trim().toLowerCase(),
            mobile: form.mobile.trim(),
            password: form.password,
            confirm_password: form.confirm_password,
          };

    try {
      const res = await fetch(`${API}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (res.ok) {
        if (authView === "login") {
          localStorage.setItem("token", data.token);
          localStorage.setItem("user", JSON.stringify(data.user));
          setToken(data.token);
          setUser(data.user);
        } else {
          setForm({
            name: "",
            email: "",
            mobile: "",
            password: "",
            confirm_password: "",
          });
          setErrors({});
          setAuthView("login");
        }
      } else {
        if (authView === "signup") {
          const errorMsg = data.detail || "Signup failed";
          if (errorMsg.toLowerCase().includes("email")) {
            setErrors({ email: errorMsg });
          } else if (errorMsg.toLowerCase().includes("mobile")) {
            setErrors({ mobile: errorMsg });
          } else {
            setErrors({ general: errorMsg });
          }
        } else {
          setErrors({ password: "Invalid email/mobile or password" });
        }
      }
    } catch (err) {
      setErrors({ general: "Cannot connect to server. Please try again later." });
    }
  };

  // ---------- AI Functions ----------
  const callAI = async (type) => {
    if (!topic.trim()) {
      setAnswer("⚠️ Please enter a topic first.");
      return;
    }
    setLoading(true);
    setAnswer("");
    setQuiz([]);
    setFlashcards([]);
    setFlippedIndex(null);
    setQuizAnswers({});
    setQuizFeedback({});
    setQuizScore(null);

    try {
      const res = await fetch(`${API}/${type}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: topic }),
      });
      const data = await res.json();
      if (res.ok) {
        if (type === "generate-quiz") setQuiz(data.quiz || []);
        else if (type === "generate-flashcards") setFlashcards(data.flashcards || []);
        else setAnswer(data.response);
        fetchHistory();
      } else {
        setAnswer(`❌ Error: ${data.detail || "Something went wrong"}`);
      }
    } catch (err) {
      setAnswer("❌ Network error. Check backend.");
    } finally {
      setLoading(false);
    }
  };

  const download = async (format) => {
    const formattedTopic = toCamelCase(topic);
    const res = await fetch(`${API}/export-${format}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ 
        content: answer.replace(/<[^>]*>/g, ""),
        topic: formattedTopic
      }),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${formattedTopic.replace(/\s+/g, '_')}_notes.${format}`;
    a.click();
  };

  // ---------- Quiz Logic ----------
  const handleQuizAnswer = (qIndex, selectedOption) => {
    if (quizFeedback[qIndex]) return;
    const question = quiz[qIndex];
    const isCorrect = selectedOption === question.correct_answer;
    setQuizAnswers({ ...quizAnswers, [qIndex]: selectedOption });
    setQuizFeedback({
      ...quizFeedback,
      [qIndex]: { isCorrect, correctAnswer: question.correct_answer },
    });
  };

  useEffect(() => {
    if (quiz.length === 0) return;
    const total = quiz.length;
    const answeredCount = Object.keys(quizFeedback).length;
    if (answeredCount === total && total > 0) {
      const correctCount = Object.values(quizFeedback).filter((fb) => fb.isCorrect).length;
      setQuizScore(correctCount);
    } else {
      setQuizScore(null);
    }
  }, [quizFeedback, quiz]);

  const toggleFlip = (idx) => {
    setFlippedIndex(flippedIndex === idx ? null : idx);
  };

  // ---------- Render Auth Page ----------
  if (!token) {
    return (
      <div className="auth-box">
        <div className="card">
          <h2>{authView === "login" ? "Welcome Back" : "Join AI Smart Buddy"}</h2>
          <form onSubmit={handleAuth}>
            {authView === "signup" && (
              <>
                <input
                  type="text"
                  name="fullname"
                  autoComplete="name"
                  placeholder="Full Name"
                  value={form.name}
                  onChange={(e) => {
                    setForm({ ...form, name: e.target.value });
                    setErrors({ ...errors, name: "" });
                  }}
                  className={errors.name ? "error-input" : ""}
                />
                {errors.name && <div className="error-text">{errors.name}</div>}
              </>
            )}

            <input
              type="text"
              name={authView === "login" ? "login_identifier" : "email"}
              autoComplete={authView === "login" ? "username" : "email"}
              placeholder={authView === "login" ? "Email or Mobile" : "Email"}
              value={form.email}
              onChange={(e) => {
                setForm({ ...form, email: e.target.value });
                setErrors({ ...errors, email: "" });
              }}
              className={errors.email ? "error-input" : ""}
            />
            {errors.email && <div className="error-text">{errors.email}</div>}

            {authView === "signup" && (
              <>
                <input
                  type="tel"
                  name="mobile"
                  autoComplete="tel"
                  placeholder="Mobile Number (10 digits)"
                  value={form.mobile}
                  onChange={(e) => {
                    setForm({ ...form, mobile: e.target.value });
                    setErrors({ ...errors, mobile: "" });
                  }}
                  className={errors.mobile ? "error-input" : ""}
                />
                {errors.mobile && <div className="error-text">{errors.mobile}</div>}
              </>
            )}

            {authView === "login" ? (
              <input
                type="password"
                name="password_login"
                autoComplete="off"
                placeholder="Password"
                value={form.password}
                onChange={(e) => {
                  setForm({ ...form, password: e.target.value });
                  setErrors({ ...errors, password: "" });
                }}
                className={errors.password ? "error-input" : ""}
              />
            ) : (
              <input
                type="password"
                name="password"
                autoComplete="new-password"
                placeholder="Password"
                value={form.password}
                onChange={(e) => {
                  setForm({ ...form, password: e.target.value });
                  setErrors({ ...errors, password: "" });
                }}
                className={errors.password ? "error-input" : ""}
              />
            )}
            {errors.password && <div className="error-text">{errors.password}</div>}

            {authView === "signup" && (
              <>
                <input
                  type="password"
                  name="confirm_password"
                  autoComplete="off"
                  placeholder="Confirm Password"
                  value={form.confirm_password}
                  onChange={(e) => {
                    setForm({ ...form, confirm_password: e.target.value });
                    setErrors({ ...errors, confirm: "" });
                  }}
                  className={errors.confirm ? "error-input" : ""}
                />
                {errors.confirm && <div className="error-text">{errors.confirm}</div>}
              </>
            )}

            {errors.general && <div className="error-text general-error">{errors.general}</div>}

            <button className="p-btn">Proceed</button>
          </form>
          <p
            className="toggle"
            onClick={() => {
              setAuthView(authView === "login" ? "signup" : "login");
              setErrors({});
              setForm({
                name: "",
                email: "",
                mobile: "",
                password: "",
                confirm_password: "",
              });
            }}
          >
            {authView === "login" ? "New? Sign Up" : "Have account? Login"}
          </p>
        </div>
      </div>
    );
  }

  // ---------- Render Main App ----------
  return (
    <div className="app-container">
      <div className={`sidebar ${sidebar ? "open" : ""}`}>
        <div className="sidebar-content">
          <button className="close-btn" onClick={() => setSidebar(false)}>✕</button>
          <div className="user-profile">
            <div className="circle" style={{ background: getLetterColor(user?.name?.[0] || "U") }}>
              {user?.name?.[0] || "?"}
            </div>
            <h4>{user?.name}</h4>
            <p className="user-id">ID: {getUserID()}</p>
            <p>Mob: {user?.mobile}</p>
          </div>
          <div className="history-section">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
              <h4>📜 Search History</h4>
              <button onClick={() => setShowClearConfirm(true)} className="clear-history-btn">Clear All</button>
            </div>
            {showClearConfirm && (
              <div className="inline-confirm">
                <span>Are you sure you want to clear all history?</span>
                <div style={{ marginTop: "8px", display: "flex", gap: "10px" }}>
                  <button onClick={clearAllHistory} className="confirm-yes">Yes, Clear</button>
                  <button onClick={() => setShowClearConfirm(false)} className="confirm-no">Cancel</button>
                </div>
              </div>
            )}
            {history.length === 0 ? (
              <p>No searches yet</p>
            ) : (
              <ul>
                {history.map((h, idx) => (
                  <li key={idx}>
                    <span onClick={() => setTopic(h.topic)} style={{ flex: 1, cursor: "pointer" }}>
                      <strong>{formatType(h.type)}</strong>: {h.topic.length > 35 ? h.topic.slice(0, 35) + "..." : h.topic}
                    </span>
                    <button onClick={() => deleteHistoryItem(h.id)} className="delete-history-btn">✕</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <button
          className="l-btn"
          onClick={() => {
            localStorage.clear();
            window.location.reload();
          }}
        >
          Logout
        </button>
      </div>

      <header>
        <button className="m-btn" onClick={() => setSidebar(true)}>☰</button>
        <h1>AI Smart Buddy 🤖</h1>
      </header>

      <div className="content">
        <input
          className="main-in"
          placeholder="What do you want to learn today?"
          onChange={(e) => setTopic(e.target.value)}
          value={topic}
        />
        <div className="btn-row">
          <button onClick={() => callAI("explain")}>Explain</button>
          <button onClick={() => callAI("generate-quiz")}>Quiz</button>
          <button onClick={() => callAI("generate-flashcards")}>Flashcards</button>
        </div>

        {loading && <h2 className="blink">Generating Content...</h2>}

        {answer && (
          <div className="ans-box">
            <div
              dangerouslySetInnerHTML={{
                __html: answer.replace(/\n/g, "<br/>").replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>"),
              }}
            />
            <div className="dl-btns">
              <button onClick={() => download("txt")}>Download TXT</button>
              <button onClick={() => download("pdf")}>Download PDF</button>
            </div>
          </div>
        )}

        {quiz.length > 0 && (
          <div className="quiz-box">
            <h3>📝 Quiz Time!</h3>
            {quiz.map((q, idx) => {
              const selected = quizAnswers[idx];
              const feedback = quizFeedback[idx];
              return (
                <div key={idx} className="quiz-question">
                  <p><strong>Q{idx + 1}:</strong> {q.question}</p>
                  <div className="quiz-options">
                    {q.options.map((opt, optIdx) => {
                      let optionClass = "";
                      if (feedback) {
                        if (opt === feedback.correctAnswer) optionClass = "correct-option";
                        if (selected === opt && !feedback.isCorrect) optionClass = "wrong-option";
                      }
                      return (
                        <label key={optIdx} className={optionClass}>
                          <input
                            type="radio"
                            name={`q${idx}`}
                            value={opt}
                            onChange={() => handleQuizAnswer(idx, opt)}
                            checked={selected === opt}
                            disabled={!!feedback}
                          />
                          {opt}
                        </label>
                      );
                    })}
                  </div>
                  {feedback && (
                    <div className="quiz-feedback">
                      {feedback.isCorrect ? "✅ Correct!" : `❌ Wrong! Correct answer: ${feedback.correctAnswer}`}
                    </div>
                  )}
                </div>
              );
            })}
            {quizScore !== null && (
              <div className="final-score">🎯 Final Score: {quizScore} / {quiz.length}</div>
            )}
          </div>
        )}

        {flashcards.length > 0 && (
          <div className="flashcards-container">
            <h3>📇 Flashcards</h3>
            <div className="flashcard-list">
              {flashcards.map((card, idx) => (
                <div
                  key={idx}
                  className={`flashcard ${flippedIndex === idx ? "flipped" : ""}`}
                  onClick={() => toggleFlip(idx)}
                >
                  <div className="flashcard-inner">
                    <div className="flashcard-front">{card.question}</div>
                    <div className="flashcard-back">{card.answer}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


