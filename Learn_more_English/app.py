import os
import json
import random
import time
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# File lưu trữ dữ liệu
FILE_PATH = "D:/Learn_more_English/vocab.json" if os.path.exists("D:/Learn_more_English/") else "vocab.json"
NOTES_PATH = "D:/Learn_more_English/grammar_notes.txt" if os.path.exists("D:/Learn_more_English/") else "grammar_notes.txt"

if not os.path.exists(FILE_PATH):
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

if not os.path.exists(NOTES_PATH):
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        f.write("# Ghi chú ngữ pháp chép tay của bạn\n\n- Cấu trúc 1: S + V + O\n- Cấu trúc 2: It takes + sb + time + to V")

def save_vocab(data):
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def detect_word_type(word):
    """Đoán từ loại dựa trên hậu tố tiếng Anh"""
    w = word.lower().strip()
    if w.endswith(('tion', 'sion', 'ment', 'ness', 'ity', 'ance', 'ence', 'ship', 'dom')):
        return 'Danh từ (n)'
    elif w.endswith(('able', 'ible', 'ful', 'less', 'ous', 'ive', 'al', 'ic')):
        return 'Tính từ (adj)'
    elif w.endswith(('ly',)):
        return 'Trạng từ (adv)'
    elif w.endswith(('ize', 'ise', 'ate', 'fy')):
        return 'Động từ (v)'
    return 'Từ vựng'

def refine_grammar_meaning(word, text):
    """Chuẩn hóa ngữ pháp cho nghĩa tiếng Việt (Ví dụ đuôi -tion -> Sự ...)"""
    if not text:
        return text
    w_lower = word.lower().strip()
    t_lower = text.lower().strip()
    
    noun_suffixes = ('tion', 'sion', 'ment', 'ness', 'ity', 'ance', 'ence', 'ship', 'dom')
    if any(w_lower.endswith(suf) for suf in noun_suffixes):
        prefixes = ('sự ', 'quá trình ', 'tính ', 'niềm ', 'việc ', 'khả năng ')
        if not any(t_lower.startswith(p) for p in prefixes):
            return f"Sự {t_lower}"
            
    return text

def read_vocab():
    """Đọc file từ vựng và tự động bổ sung trường còn thiếu"""
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            updated = False
            base_time = int(time.time() * 1000)
            for idx, w in enumerate(data):
                if 'id' not in w:
                    w['id'] = base_time + idx
                    updated = True
                if 'level' not in w:
                    w['level'] = 1
                    updated = True
                if 'created_at' not in w:
                    w['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    updated = True
                if 'type' not in w:
                    w['type'] = detect_word_type(w.get('english', ''))
                    updated = True
            
            if updated:
                save_vocab(data)
            return data
    except Exception:
        return []

# ====== CHỨC NĂNG DỊCH THÔNG MINH ======
def translate_soha(word):
    word = word.strip()
    if not word:
        return "", ""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    raw_translation = ""

    # 1. Google Translate API
    try:
        gt_url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=vi&dt=t&q={urllib.parse.quote(word)}"
        res = requests.get(gt_url, headers=headers, timeout=4)
        if res.status_code == 200:
            data = res.json()
            if data and data[0] and data[0][0] and data[0][0][0]:
                raw_translation = data[0][0][0]
    except Exception:
        pass

    # 2. MyMemory API
    if not raw_translation:
        try:
            mm_url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(word)}&langpair=en|vi"
            res = requests.get(mm_url, headers=headers, timeout=4)
            if res.status_code == 200:
                data = res.json()
                text = data.get('responseData', {}).get('translatedText', '')
                if text and text.lower() != word.lower():
                    raw_translation = text
        except Exception:
            pass

    # 3. Soha Dict
    if not raw_translation:
        try:
            url = f"http://tratu.soha.vn/dict/en_vn/{urllib.parse.quote(word)}"
            res = requests.get(url, headers=headers, timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                meanings = []
                for tag in soup.select('div.m-top20 ul li, h5, div.section-5 h5'):
                    text = tag.get_text(strip=True)
                    if text and not text.startswith("Xem từ") and not text.startswith("Từ điển") and len(text) < 80:
                        meanings.append(text)
                if meanings:
                    raw_translation = ", ".join(meanings[:3])
        except Exception:
            pass

    final_translation = refine_grammar_meaning(word, raw_translation)
    word_type = detect_word_type(word)
    return final_translation, word_type

# ====== API ENDPOINTS ======

@app.route('/api/translate', methods=['POST'])
def api_translate():
    data = request.json or {}
    english = data.get('english', '')
    vietnamese, word_type = translate_soha(english)
    return jsonify({'vietnamese': vietnamese, 'type': word_type})

@app.route('/api/words', methods=['GET'])
def get_words():
    words = read_vocab()
    words.sort(key=lambda x: str(x.get('created_at', '')), reverse=True)
    return jsonify(words)

@app.route('/api/words', methods=['POST'])
def add_word():
    data = request.json or {}
    english = data.get('english', '').strip()
    vietnamese = data.get('vietnamese', '').strip()
    
    if not english or not vietnamese:
        return jsonify({'error': 'Vui lòng nhập đủ Anh và Việt'}), 400

    words = read_vocab()
    new_item = {
        'id': int(time.time() * 1000),
        'english': english,
        'vietnamese': vietnamese,
        'type': detect_word_type(english),
        'level': 1,
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    words.append(new_item)
    save_vocab(words)
    return jsonify({'success': True, 'word': new_item})

@app.route('/api/words/<int:word_id>', methods=['DELETE'])
def delete_word(word_id):
    words = read_vocab()
    words = [w for w in words if w.get('id') != word_id]
    save_vocab(words)
    return jsonify({'success': True})

@app.route('/api/quiz/next', methods=['GET'])
def get_quiz_question():
    words = read_vocab()
    if not words:
        return jsonify({'empty': True})

    weights = [max(1, 7 - w.get('level', 1)) for w in words]
    target_word = random.choices(words, weights=weights, k=1)[0]
    
    level = target_word.get('level', 1)
    target_id = target_word.get('id')
    
    options = []
    if level in [1, 2]:
        other_words = [w for w in words if w.get('id') != target_id]
        random.shuffle(other_words)
        distractors = other_words[:3]
        
        if level == 1:
            options = [target_word['vietnamese']] + [d['vietnamese'] for d in distractors]
        else:
            options = [target_word['english']] + [d['english'] for d in distractors]
        random.shuffle(options)

    return jsonify({
        'empty': False,
        'id': target_id,
        'english': target_word['english'],
        'vietnamese': target_word['vietnamese'],
        'level': level,
        'options': options
    })

@app.route('/api/quiz/update-level', methods=['POST'])
def update_word_level():
    data = request.json or {}
    word_id = data.get('id')
    is_correct = data.get('is_correct', False)

    words = read_vocab()
    for w in words:
        if w.get('id') == word_id:
            if is_correct:
                w['level'] = min(6, w.get('level', 1) + 1)
            else:
                w['level'] = 1  # Trả lời sai -> Về lại Cấp 1 ôn lại
            break
    save_vocab(words)
    return jsonify({'success': True})

@app.route('/api/notes', methods=['GET', 'POST'])
def handle_notes():
    if request.method == 'POST':
        content = request.json.get('content', '')
        with open(NOTES_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True})
    else:
        content = ""
        if os.path.exists(NOTES_PATH):
            with open(NOTES_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
        return jsonify({'content': content})

# ====== GIAO DIỆN WEB UI ======
@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Học Từ Vựng & Ngữ Pháp Tiếng Anh (6 Cấp Độ)</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            --card-bg: rgba(30, 41, 59, 0.7);
            --accent-color: #38bdf8;
        }
        body {
            background: var(--bg-gradient);
            color: #f8fafc;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
            padding-bottom: 40px;
        }
        .glass-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        .nav-pills .nav-link {
            color: #94a3b8;
            font-weight: 600;
            border-radius: 12px;
            padding: 12px 24px;
            transition: all 0.3s ease;
        }
        .nav-pills .nav-link.active {
            background: #0284c7;
            color: white;
            box-shadow: 0 4px 15px rgba(2, 132, 199, 0.4);
        }
        .btn-custom {
            background: linear-gradient(135deg, #38bdf8 0%, #0284c7 100%);
            border: none;
            color: white;
            font-weight: 600;
            border-radius: 10px;
        }
        .btn-custom:hover {
            opacity: 0.9;
            color: white;
        }
        .level-badge {
            font-size: 0.85rem;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: bold;
        }
        .level-1 { background: #ef4444; color: white; }
        .level-2 { background: #f97316; color: white; }
        .level-3 { background: #eab308; color: #ffffff !important; }
        .level-4 { background: #06b6d4; color: white; }
        .level-5 { background: #3b82f6; color: white; }
        .level-6 { background: #22c55e; color: white; }
        
        /* CHỮ MỜ THÀNH MÀU TRẮNG XÁM SÁNG */
        .text-muted, small, .small, label, .form-text {
            color: #cbd5e1 !important;
        }

        .quiz-card-option {
            background: rgba(51, 65, 85, 0.8);
            border: 2px solid transparent;
            border-radius: 12px;
            padding: 15px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 1.1rem;
        }
        .quiz-card-option:hover {
            border-color: var(--accent-color);
            transform: translateY(-2px);
        }
        .hint-text {
            font-family: 'Consolas', monospace;
            font-size: 1.8rem;
            letter-spacing: 6px;
            color: #38bdf8;
            background: rgba(15, 23, 42, 0.6);
            padding: 10px 20px;
            border-radius: 10px;
            display: inline-block;
        }
        textarea.notes-editor {
            background: #0f172a;
            color: #e2e8f0;
            border: 1px solid #334155;
            border-radius: 12px;
            font-family: 'Consolas', 'Courier New', monospace;
            padding: 15px;
            font-size: 1rem;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2><i class="fa-solid fa-graduation-cap text-info me-2"></i>English Learning Pro</h2>
            <span class="badge bg-secondary" id="total-words-badge">0 từ vựng</span>
        </div>

        <ul class="nav nav-pills mb-4 glass-card p-2 justify-content-center" id="mainTab" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" id="add-tab" data-bs-toggle="pill" data-bs-target="#tab-add">
                    <i class="fa-solid fa-plus me-2"></i>Thêm & Tra Từ
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="list-tab" data-bs-toggle="pill" data-bs-target="#tab-list" onclick="loadVocabList()">
                    <i class="fa-solid fa-list me-2"></i>Danh Sách Từ
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="quiz-tab" data-bs-toggle="pill" data-bs-target="#tab-quiz" onclick="loadNextQuiz()">
                    <i class="fa-solid fa-brain me-2"></i>Kiểm Tra 6 Cấp Độ
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="notes-tab" data-bs-toggle="pill" data-bs-target="#tab-notes" onclick="loadNotes()">
                    <i class="fa-solid fa-book-bookmark me-2"></i>Ghi Chú Ngữ Pháp
                </button>
            </li>
        </ul>

        <div class="tab-content">
            <!-- TAB 1: THÊM TỪ -->
            <div class="tab-pane fade show active" id="tab-add">
                <div class="row justify-content-center">
                    <div class="col-md-7">
                        <div class="glass-card p-4">
                            <h4 class="mb-3 text-info"><i class="fa-solid fa-magnifying-glass-plus me-2"></i>Thêm từ & Dịch tự động</h4>
                            <form id="form-add-word" onsubmit="handleAddWord(event)">
                                <div class="mb-3">
                                    <label class="form-label">Từ Tiếng Anh:</label>
                                    <div class="input-group">
                                        <input type="text" id="input-en" class="form-control form-control-lg bg-dark text-white border-secondary" placeholder="Ví dụ: distribution..." required oninput="autoTranslate()">
                                        <button class="btn btn-outline-info" type="button" onclick="autoTranslate()">
                                            <i class="fa-solid fa-language"></i> Dịch Chuẩn Ngữ Pháp
                                        </button>
                                    </div>
                                    <small class="text-muted" id="translate-status"></small>
                                </div>
                                <div class="mb-4">
                                    <label class="form-label">Nghĩa Tiếng Việt (Tự động chuẩn hóa hậu tố):</label>
                                    <input type="text" id="input-vi" class="form-control form-control-lg bg-dark text-white border-secondary" placeholder="Nghĩa tiếng Việt..." required>
                                </div>
                                <button type="submit" class="btn btn-custom btn-lg w-100">
                                    <i class="fa-solid fa-download me-2"></i>Lưu Vào Bộ Từ Vựng
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 2: DANH SÁCH TỪ + BỘ LỌC SẮP XẾP -->
            <div class="tab-pane fade" id="tab-list">
                <div class="glass-card p-4">
                    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                        <h4 class="text-info mb-0"><i class="fa-solid fa-clock-rotate-left me-2"></i>Danh Sách Từ Vựng Đã Nhập</h4>
                        <div class="d-flex align-items-center">
                            <label class="me-2 mb-0 text-light small fw-bold">Sắp xếp theo:</label>
                            <select id="sort-select" class="form-select bg-dark text-light border-secondary" style="width: 220px;" onchange="loadVocabList()">
                                <option value="date_desc">📅 Mới nhất (Ngày)</option>
                                <option value="date_asc">📅 Cũ nhất (Ngày)</option>
                                <option value="level_asc">📈 Cấp độ: Thấp → Cao</option>
                                <option value="level_desc">📉 Cấp độ: Cao → Thấp</option>
                            </select>
                        </div>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-dark table-hover align-middle">
                            <thead>
                                <tr>
                                    <th>STT</th>
                                    <th>English</th>
                                    <th>Từ Loại</th>
                                    <th>Nghĩa Tiếng Việt</th>
                                    <th>Cấp độ thuộc</th>
                                    <th>Ngày tạo</th>
                                    <th>Thao tác</th>
                                </tr>
                            </thead>
                            <tbody id="vocab-table-body">
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- TAB 3: KIỂM TRA -->
            <div class="tab-pane fade" id="tab-quiz">
                <div class="row justify-content-center">
                    <div class="col-md-8">
                        <div class="glass-card p-4 text-center" id="quiz-container">
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 4: GHI CHÚ -->
            <div class="tab-pane fade" id="tab-notes">
                <div class="glass-card p-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h4 class="text-info"><i class="fa-solid fa-pen-to-square me-2"></i>Sổ Tay Ghi Chú Ngữ Pháp Chép Tay</h4>
                        <button class="btn btn-custom" onclick="saveNotes()">
                            <i class="fa-solid fa-floppy-disk me-2"></i>Lưu Ghi Chú
                        </button>
                    </div>
                    <textarea id="notes-content" class="form-control notes-editor" rows="16" placeholder="Ghi chép công thức, cấu trúc ngữ pháp tại đây..."></textarea>
                    <div class="text-end mt-2">
                        <small class="text-success" id="notes-status"></small>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let translateTimeout = null;

        document.addEventListener("DOMContentLoaded", function () {
            const listTabBtn = document.getElementById('list-tab');
            if (listTabBtn) {
                listTabBtn.addEventListener('shown.bs.tab', function () {
                    loadVocabList();
                });
            }
        });

        // Hàm tạo gợi ý che ký tự (Hỗ trợ Cấp 4 & Cấp 5)
        function generateHint(word, percent) {
            let chars = word.split('');
            let letterIndices = [];
            chars.forEach((c, i) => {
                if (/[a-zA-Z]/.test(c)) letterIndices.push(i);
            });
            
            let revealCount = Math.round(letterIndices.length * percent);
            if (percent > 0 && revealCount === 0 && letterIndices.length > 0) revealCount = 1;

            let shuffled = [...letterIndices].sort(() => 0.5 - Math.random());
            let revealedIndices = new Set(shuffled.slice(0, revealCount));

            return chars.map((c, i) => {
                if (!/[a-zA-Z]/.test(c)) return c;
                return revealedIndices.has(i) ? c : '_';
            }).join(' ');
        }

        function autoTranslate() {
            clearTimeout(translateTimeout);
            const enText = document.getElementById('input-en').value.trim();
            const statusEl = document.getElementById('translate-status');

            if (!enText) {
                statusEl.innerText = '';
                return;
            }

            statusEl.innerText = '⏳ Đang tra dịch & phân tích ngữ pháp...';

            translateTimeout = setTimeout(() => {
                fetch('/api/translate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({english: enText})
                })
                .then(res => res.json())
                .then(data => {
                    if (data.vietnamese) {
                        document.getElementById('input-vi').value = data.vietnamese;
                        statusEl.innerText = `✅ Nghĩa gợi ý [${data.type || 'Từ vựng'}]: ${data.vietnamese}`;
                    } else {
                        statusEl.innerText = '⚠️ Không tìm thấy nghĩa tự động, vui lòng tự nhập.';
                    }
                })
                .catch(() => { statusEl.innerText = '⚠️ Lỗi kết nối dịch tự động.'; });
            }, 600);
        }

        function handleAddWord(e) {
            e.preventDefault();
            const en = document.getElementById('input-en').value.trim();
            const vi = document.getElementById('input-vi').value.trim();

            fetch('/api/words', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({english: en, vietnamese: vi})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('input-en').value = '';
                    document.getElementById('input-vi').value = '';
                    document.getElementById('translate-status').innerText = '';
                    loadVocabList();
                    alert('Thêm từ vựng mới thành công!');
                }
            });
        }

        function loadVocabList() {
            fetch('/api/words')
            .then(res => res.json())
            .then(words => {
                document.getElementById('total-words-badge').innerText = words.length + ' từ vựng';
                
                const sortSelect = document.getElementById('sort-select');
                const sortType = sortSelect ? sortSelect.value : 'date_desc';

                if (sortType === 'date_desc') {
                    words.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
                } else if (sortType === 'date_asc') {
                    words.sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || '')));
                } else if (sortType === 'level_asc') {
                    words.sort((a, b) => (a.level || 1) - (b.level || 1));
                } else if (sortType === 'level_desc') {
                    words.sort((a, b) => (b.level || 1) - (a.level || 1));
                }

                const tbody = document.getElementById('vocab-table-body');
                tbody.innerHTML = '';
                
                words.forEach((w, index) => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${index + 1}</td>
                        <td class="fw-bold text-info">${w.english}</td>
                        <td><span class="badge bg-secondary">${w.type || 'Từ vựng'}</span></td>
                        <td>${w.vietnamese}</td>
                        <td><span class="level-badge level-${w.level}">Cấp ${w.level} / 6</span></td>
                        <td class="text-light small">${w.created_at || 'Mới đây'}</td>
                        <td>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteWord(${w.id})">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            });
        }

        function deleteWord(id) {
            if (confirm('Bạn có chắc muốn xóa từ này?')) {
                fetch('/api/words/' + id, { method: 'DELETE' })
                .then(() => loadVocabList());
            }
        }

        let currentQuiz = null;

        function loadNextQuiz() {
            const container = document.getElementById('quiz-container');
            container.innerHTML = '<h4>⏳ Đang tạo câu hỏi...</h4>';

            fetch('/api/quiz/next')
            .then(res => res.json())
            .then(quiz => {
                if (quiz.empty) {
                    container.innerHTML = '<h4>📚 Chưa có từ vựng! Hãy qua Tab "Thêm Từ" để bổ sung nhé.</h4>';
                    return;
                }
                currentQuiz = quiz;
                renderQuizUI(quiz);
            });
        }

        function renderQuizUI(quiz) {
            const container = document.getElementById('quiz-container');
            let html = `<div class="mb-3"><span class="level-badge level-${quiz.level}">BÀI KIỂM TRA CẤP ${quiz.level} / 6</span></div>`;
            
            // CẤP 1: Trắc nghiệm Anh -> Chọn Việt
            if (quiz.level === 1) {
                html += `<h3 class="mb-4">Từ: <span class="text-info">${quiz.english}</span> có nghĩa là gì?</h3>`;
                html += `<div class="row g-3">`;
                quiz.options.forEach(opt => {
                    html += `
                    <div class="col-md-6">
                        <div class="quiz-card-option" onclick="checkChoice('${escapeHtml(opt)}')">${opt}</div>
                    </div>`;
                });
                html += `</div>`;
            } 
            // CẤP 2: Trắc nghiệm Việt -> Chọn Anh
            else if (quiz.level === 2) {
                html += `<h3 class="mb-4">Nghĩa: <span class="text-warning">${quiz.vietnamese}</span> ứng với từ Tiếng Anh nào?</h3>`;
                html += `<div class="row g-3">`;
                quiz.options.forEach(opt => {
                    html += `
                    <div class="col-md-6">
                        <div class="quiz-card-option" onclick="checkChoice('${escapeHtml(opt)}')">${opt}</div>
                    </div>`;
                });
                html += `</div>`;
            }
            // CẤP 3: Gõ Tiếng Việt cho từ Tiếng Anh
            else if (quiz.level === 3) {
                html += `<h3 class="mb-3">Hãy điền nghĩa Tiếng Việt cho từ: <span class="text-info">${quiz.english}</span></h3>`;
                html += `
                <div class="col-md-8 mx-auto mt-4">
                    <input type="text" id="quiz-input" class="form-control form-control-lg text-center bg-dark text-white mb-3" placeholder="Nhập nghĩa tiếng Việt..." onkeydown="if(event.key==='Enter') checkTyping()">
                    <button class="btn btn-custom btn-lg w-100" onclick="checkTyping()">Trả Lời</button>
                </div>`;
            }
            // CẤP 4: Gõ Tiếng Anh (Gợi ý 50% ký tự)
            else if (quiz.level === 4) {
                const hint = generateHint(quiz.english, 0.5);
                html += `<h3 class="mb-2">Nghĩa: <span class="text-warning">${quiz.vietnamese}</span></h3>`;
                html += `<p class="text-light small">Gợi ý 50% chữ cái:</p>`;
                html += `<div class="hint-text mb-4">${hint}</div>`;
                html += `
                <div class="col-md-8 mx-auto">
                    <input type="text" id="quiz-input" class="form-control form-control-lg text-center bg-dark text-white mb-3" placeholder="Gõ từ Tiếng Anh..." onkeydown="if(event.key==='Enter') checkTyping()">
                    <button class="btn btn-custom btn-lg w-100" onclick="checkTyping()">Trả Lời</button>
                </div>`;
            }
            // CẤP 5: Gõ Tiếng Anh (Gợi ý 20% ký tự)
            else if (quiz.level === 5) {
                const hint = generateHint(quiz.english, 0.2);
                html += `<h3 class="mb-2">Nghĩa: <span class="text-warning">${quiz.vietnamese}</span></h3>`;
                html += `<p class="text-light small">Gợi ý 20% chữ cái:</p>`;
                html += `<div class="hint-text mb-4">${hint}</div>`;
                html += `
                <div class="col-md-8 mx-auto">
                    <input type="text" id="quiz-input" class="form-control form-control-lg text-center bg-dark text-white mb-3" placeholder="Gõ từ Tiếng Anh..." onkeydown="if(event.key==='Enter') checkTyping()">
                    <button class="btn btn-custom btn-lg w-100" onclick="checkTyping()">Trả Lời</button>
                </div>`;
            }
            // CẤP 6: Gõ Tiếng Anh (Không gợi ý)
            else if (quiz.level === 6) {
                html += `<h3 class="mb-2">Nghĩa: <span class="text-warning">${quiz.vietnamese}</span></h3>`;
                html += `<p class="text-danger fw-bold mb-4">🔥 CẤP ĐỘ CAO NHẤT: Không gợi ý chữ cái (Tự nhớ 100%)</p>`;
                html += `
                <div class="col-md-8 mx-auto">
                    <input type="text" id="quiz-input" class="form-control form-control-lg text-center bg-dark text-white mb-3" placeholder="Nhập chính xác từ Tiếng Anh..." onkeydown="if(event.key==='Enter') checkTyping()">
                    <button class="btn btn-custom btn-lg w-100" onclick="checkTyping()">Trả Lời</button>
                </div>`;
            }

            container.innerHTML = html;
            if (document.getElementById('quiz-input')) {
                document.getElementById('quiz-input').focus();
            }
        }

        function escapeHtml(str) {
            return str.replace(/'/g, "\\'");
        }

        function checkChoice(userAnswer) {
            let isCorrect = false;
            if (currentQuiz.level === 1) isCorrect = (userAnswer.trim().toLowerCase() === currentQuiz.vietnamese.trim().toLowerCase());
            if (currentQuiz.level === 2) isCorrect = (userAnswer.trim().toLowerCase() === currentQuiz.english.trim().toLowerCase());
            handleResult(isCorrect);
        }

        function checkTyping() {
            const inputVal = document.getElementById('quiz-input').value.trim().toLowerCase();
            let isCorrect = false;
            if (currentQuiz.level === 3) {
                isCorrect = (inputVal === currentQuiz.vietnamese.trim().toLowerCase());
            } else if (currentQuiz.level >= 4) {
                isCorrect = (inputVal === currentQuiz.english.trim().toLowerCase());
            }
            handleResult(isCorrect);
        }

        // ====== XỬ LÝ KẾT QUẢ KIỂM TRA ======
        function handleResult(isCorrect) {
            const container = document.getElementById('quiz-container');
            
            if (isCorrect) {
                container.innerHTML = `
                    <div class="text-success mb-3"><i class="fa-solid fa-circle-check fa-4x"></i></div>
                    <h2>CHÍNH XÁC! 🎉</h2>
                    <p class="fs-5">Từ vựng đã tăng lên <strong>Cấp ${Math.min(6, currentQuiz.level + 1)} / 6</strong>!</p>
                `;
                // ĐÚNG: Tự động chuyển câu sau 2 giây
                setTimeout(loadNextQuiz, 2000);
            } else {
                container.innerHTML = `
                    <div class="text-danger mb-3"><i class="fa-solid fa-circle-xmark fa-4x"></i></div>
                    <h2>CHƯA CHÍNH XÁC! ❌</h2>
                    <div class="my-3 p-3 bg-dark rounded border border-danger">
                        <p class="fs-4 mb-1 text-info fw-bold">${currentQuiz.english}</p>
                        <p class="fs-5 mb-0 text-warning">👉 ${currentQuiz.vietnamese}</p>
                    </div>
                    <p class="text-light small mb-4">Từ này đã về lại Cấp 1 để luyện ôn lại chắc chắn hơn.</p>
                    <!-- SAI: Đợi người dùng tự nhấn nút Next -->
                    <div class="col-md-8 mx-auto">
                        <button class="btn btn-custom btn-lg w-100" onclick="loadNextQuiz()">
                            Tiếp Theo <i class="fa-solid fa-arrow-right ms-2"></i>
                        </button>
                    </div>
                `;
                // KHÔNG gọi setTimeout khi sai
            }

            fetch('/api/quiz/update-level', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentQuiz.id, is_correct: isCorrect})
            });
        }

        function loadNotes() {
            fetch('/api/notes')
            .then(res => res.json())
            .then(data => {
                document.getElementById('notes-content').value = data.content || '';
            });
        }

        function saveNotes() {
            const content = document.getElementById('notes-content').value;
            fetch('/api/notes', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({content: content})
            })
            .then(res => res.json())
            .then(() => {
                const status = document.getElementById('notes-status');
                status.innerText = '✓ Đã lưu ghi chú thành công!';
                setTimeout(() => status.innerText = '', 3000);
            });
        }

        loadVocabList();
    </script>
</body>
</html>
    ''')

if __name__ == '__main__':
    print("====================================================")
    print(" App Học Từ Vựng & Ngữ Pháp Tiếng Anh đang chạy!")
    print(" Mở trình duyệt truy cập: http://localhost:5000")
    print("====================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)