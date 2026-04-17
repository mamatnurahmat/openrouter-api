# GitOps Manager AI Agent

GitOps Manager adalah AI Agent berbasis CrewAI dan OpenRouter yang bertugas mengotomatisasi pekerjaan DevOps dan GitOps. Agent ini mampu melakukan perubahan pada repository, seperti update file konfigurasi YAML, lalu secara otomatis membuat commit, branch, Pull Request, dan mengirim notifikasi.

## Prasyarat

Sebelum menjalankan GitOps Agent, pastikan sistem Anda telah memiliki:

1. **Python 3.9+**
2. **Git** (sudah terkonfigurasi user.name dan user.email)
3. **GitHub CLI (`gh`)**: Sudah login dengan menjalankan `gh auth login`
4. **yq**: Utility untuk membaca dan mengupdate file YAML dari command line.
5. **cURL**: Untuk mengirim HTTP request ke `ntfy.sh`.

## Instalasi

1. Pastikan Anda berada di root direktori project ini.
2. Karena Anda menggunakan environment yang di-manage oleh OS/Nix (PEP 668 `externally-managed-environment`), Anda tidak bisa menjalankan `pip install` secara global. Anda disarankan menggunakan **Python Virtual Environment (`venv`)**:

   ```bash
   # Buat virtual environment bernama 'venv'
   python -m venv venv
   
   # Aktifkan virtual environment
   # Untuk Mac/Linux (Zsh/Bash):
   source venv/bin/activate
   
   # Setelah aktif (akan ada prefix '(venv)' di terminal), jalankan instalasi:
   pip install -r requirements.txt
   ```
   *Dependensi utama: `crewai`, `crewai-tools`, `python-dotenv`.*

## Konfigurasi Kredensial

Agent ini menggunakan `.env` untuk menyimpan kredensial dengan aman agar tidak ter-commit ke repository.

1. Buat file `.env` di direktori yang sama dengan script `gitops_agent.py` jika belum ada.
2. Tambahkan variabel berikut ke dalam `.env`:

   ```env
   # API Key OpenRouter Anda
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxx
   
   # Topik ntfy.sh untuk mengirim notifikasi
   NTFY_TOPIC=gitops_alerts_topik_anda
   ```

## Cara Penggunaan

1. Buka file `gitops_agent.py`.
2. Modifikasi `description` pada objek `gitops_task` sesuai dengan operasi yang ingin Anda jalankan. Contoh:

   ```python
   gitops_task = Task(
       description=dedent('''\
           Skenario: Update versi image pada file deployment k8s untuk Qoin Digital.
           
           Langkah-langkah:
           1. **Clone Repo**: Clone repository "Qoin-Digital-Indonesia/gitops-k8s" menggunakan GitHub CLI (gh) dengan branch "develop-qoin" ke folder "qoin-gitops-workdir".
           2. **Create Branch**: Di dalam folder "qoin-gitops-workdir", buat branch baru bernama 'feat/update-be-sample-manager-image'.
           3. **Update YAML**: Di dalam folder "qoin-gitops-workdir", gunakan yq untuk mengubah file "develop-devops/devops-be-sample-manager_deployment.yaml". Ubah tag image menjadi "qoin/be-sample-manager:v1.2.3".
           4. **Validasi Helm**: Lakukan linting jika menggunakan Helm (contoh: `helm lint .`).
           5. **Commit & Push**: Lakukan commit perubahan dengan pesan "feat: update be-sample-manager image to v1.2.3" lalu push.
           6. **Pull Request**: Buat Pull Request.
           7. **Notifikasi**: Kirim notifikasi via ntfy.sh.
       '''),
       ...
   )
   ```

3. Jalankan script:

   ```bash
   python gitops_agent.py
   ```

## Workflow Agent

1. **Clone Repo**: Agent mendownload (clone) target repositori dan masuk ke branch yang sesuai.
2. **Create Branch**: Agent membuat dan pindah ke branch baru untuk pengerjaan fitur menggunakan `git checkout -b`.
3. **Update YAML**: Agent mencari file YAML yang dituju dan mengupdate value-nya menggunakan perintah `yq`.
4. **Helm Tool**: Agen memiliki akses ke perintah Helm untuk memvalidasi manifest k8s.
5. **Commit & Push**: Agent merekam perubahan (`git add`, `git commit`) lalu melakukan push ke origin repository.
6. **Pull Request**: Agent menggunakan `gh pr create` untuk membuka Pull Request di GitHub.
7. **Notification**: Agent mengirim notifikasi status menggunakan `curl` via layanan `ntfy.sh`.
