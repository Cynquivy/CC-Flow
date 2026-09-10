import { spawn } from 'node:child_process'
import path from 'node:path'

const isWin = process.platform === 'win32'
const backendDir = path.join(process.cwd(), 'backend')
const pythonBin = path.join(
  backendDir,
  '.venv',
  isWin ? 'Scripts' : 'bin',
  isWin ? 'python.exe' : 'python',
)

const child = spawn(pythonBin, ['-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000'], {
  cwd: backendDir,
  stdio: 'inherit',
})

child.on('exit', (code) => process.exit(code ?? 0))
