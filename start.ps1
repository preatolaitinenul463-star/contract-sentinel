# Contract Sentinel - One-click Startup Script
# 合同哨兵 - 一键启动脚本

param(
    [switch]$NoFrontend,
    [switch]$NoBackend,
    [switch]$DockerOnly,
    [Alias("h")]
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_DIR = Join-Path $SCRIPT_DIR "backend"
$FRONTEND_DIR = Join-Path $SCRIPT_DIR "frontend"

$BACKEND_PROCESS = $null
$FRONTEND_PROCESS = $null

function Write-Info($message) {
    Write-Host "[INFO]  $message" -ForegroundColor Cyan
}

function Write-Success($message) {
    Write-Host "[ OK ]  $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "[WARN]  $message" -ForegroundColor Yellow
}

function Write-Err($message) {
    Write-Host "[ERR ]  $message" -ForegroundColor Red
}

function Test-CommandExists($command) {
    $null -ne (Get-Command $command -ErrorAction SilentlyContinue)
}

function Ensure-Python {
    if (Test-CommandExists "python") {
        $version = python --version 2>&1
        Write-Success "Python is installed ($version)"
        return
    }
    Write-Err "Python is not installed. Please install Python 3.12+"
    exit 1
}

function Ensure-Node {
    if (Test-CommandExists "node") {
        $version = node --version 2>&1
        Write-Success "Node.js is installed ($version)"
        return
    }
    Write-Err "Node.js is not installed. Please install Node.js 20+"
    exit 1
}

function Ensure-Docker {
    if (Test-CommandExists "docker") {
        Write-Success "Docker is installed"
        return
    }
    Write-Warn "Docker is not installed. Database services will need manual setup."
}

function Start-DockerServices {
    Write-Info "Starting Docker services (PostgreSQL + Redis)..."
    Push-Location $SCRIPT_DIR
    try {
        docker-compose up -d postgres redis
        Write-Success "Docker services started"
        # Wait for services to be ready
        Start-Sleep -Seconds 5
    } catch {
        Write-Warn "Failed to start Docker services: $_"
        Write-Warn "Please ensure PostgreSQL and Redis are running manually."
    } finally {
        Pop-Location
    }
}

function Setup-Backend {
    if (-not (Test-Path $BACKEND_DIR)) {
        Write-Err "Backend directory not found: $BACKEND_DIR"
        return
    }
    
    Write-Info "Setting up Python virtual environment..."
    Push-Location $BACKEND_DIR
    try {
        # Create virtual environment if not exists
        if (-not (Test-Path ".venv")) {
            python -m venv .venv
            Write-Success "Virtual environment created"
        }
        
        # Activate and install dependencies
        & ".\.venv\Scripts\Activate.ps1"
        pip install -r requirements.txt -q
        Write-Success "Python dependencies installed"
        
        # Run database migrations
        Write-Info "Running database migrations..."
        python -m alembic upgrade head
        Write-Success "Database migrations complete"
    } catch {
        Write-Err "Failed to setup backend: $_"
    } finally {
        Pop-Location
    }
}

function Setup-Frontend {
    if (-not (Test-Path $FRONTEND_DIR)) {
        Write-Err "Frontend directory not found: $FRONTEND_DIR"
        return
    }
    
    Write-Info "Installing frontend dependencies..."
    Push-Location $FRONTEND_DIR
    try {
        npm install
        Write-Success "Frontend dependencies installed"
    } catch {
        Write-Err "Failed to setup frontend: $_"
    } finally {
        Pop-Location
    }
}

function Start-Backend {
    if (-not (Test-Path $BACKEND_DIR)) {
        Write-Warn "Backend directory not found; skipping backend start"
        return
    }
    
    Write-Info "Starting backend server..."
    Push-Location $BACKEND_DIR
    try {
        & ".\.venv\Scripts\Activate.ps1"
        $script:BACKEND_PROCESS = Start-Process -FilePath "python" `
            -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000" `
            -NoNewWindow -PassThru
        Write-Info "Backend PID: $($script:BACKEND_PROCESS.Id)"
        Write-Success "Backend started at http://localhost:8000"
    } catch {
        Write-Err "Failed to start backend: $_"
    } finally {
        Pop-Location
    }
}

function Start-Frontend {
    if (-not (Test-Path $FRONTEND_DIR)) {
        Write-Warn "Frontend directory not found; skipping frontend start"
        return
    }
    
    Write-Info "Starting frontend dev server..."
    Push-Location $FRONTEND_DIR
    try {
        $script:FRONTEND_PROCESS = Start-Process -FilePath "npm" `
            -ArgumentList "run", "dev" `
            -NoNewWindow -PassThru
        Write-Info "Frontend PID: $($script:FRONTEND_PROCESS.Id)"
        Write-Success "Frontend started at http://localhost:3000"
    } catch {
        Write-Err "Failed to start frontend: $_"
    } finally {
        Pop-Location
    }
}

function Cleanup {
    Write-Host ""
    Write-Info "Stopping services..."
    
    if ($script:FRONTEND_PROCESS -and -not $script:FRONTEND_PROCESS.HasExited) {
        try {
            Stop-Process -Id $script:FRONTEND_PROCESS.Id -Force -ErrorAction SilentlyContinue
        } catch { }
    }
    
    if ($script:BACKEND_PROCESS -and -not $script:BACKEND_PROCESS.HasExited) {
        try {
            Stop-Process -Id $script:BACKEND_PROCESS.Id -Force -ErrorAction SilentlyContinue
        } catch { }
    }
    
    Write-Success "Services stopped"
}

function Print-Usage {
    Write-Host @"
Usage: .\start.ps1 [options]

Contract Sentinel - 合同哨兵启动脚本

Options:
  -NoFrontend     只启动后端
  -NoBackend      只启动前端
  -DockerOnly     只启动 Docker 服务 (PostgreSQL + Redis)
  -Help, -h       显示帮助信息

Examples:
  .\start.ps1                 # 启动全部服务
  .\start.ps1 -NoFrontend     # 只启动后端
  .\start.ps1 -DockerOnly     # 只启动数据库

访问地址:
  前端: http://localhost:3000
  后端: http://localhost:8000
  API 文档: http://localhost:8000/docs
"@
}

# Main
Register-EngineEvent PowerShell.Exiting -Action { Cleanup } | Out-Null

try {
    if ($Help) {
        Print-Usage
        exit 0
    }
    
    # Check prerequisites
    Ensure-Python
    Ensure-Node
    Ensure-Docker
    
    # Start Docker services
    Start-DockerServices
    
    if ($DockerOnly) {
        Write-Success "Docker services are running"
        exit 0
    }
    
    # Setup
    if (-not $NoBackend) {
        Setup-Backend
    }
    if (-not $NoFrontend) {
        Setup-Frontend
    }
    
    # Start services
    if (-not $NoBackend) {
        Start-Backend
        Start-Sleep -Seconds 3
    }
    if (-not $NoFrontend) {
        Start-Frontend
    }
    
    Write-Host ""
    Write-Success "All services started!"
    Write-Host ""
    Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Green
    Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Green
    Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Green
    Write-Host ""
    Write-Info "Press Ctrl+C to stop all services..."
    
    # Wait
    while ($true) {
        Start-Sleep -Seconds 1
    }
} catch {
    Write-Err "An error occurred: $_"
    exit 1
} finally {
    Cleanup
}
