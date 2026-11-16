# Network and web

Never send secrets or private data to a service the user did not name. Do not pipe a downloaded script into `Invoke-Expression`.

## HTTP

```powershell
Invoke-RestMethod https://api.example.com/items                 # parses JSON/XML into objects
Invoke-RestMethod https://api.example.com/items -Headers @{ Authorization = "Bearer $env:API_TOKEN" }
Invoke-RestMethod https://api.example.com/items -Method Post -ContentType 'application/json' -Body (@{ name = 'x' } | ConvertTo-Json -Depth 5)
Invoke-RestMethod -Uri $u -Method Put -Body $json -ContentType 'application/json; charset=utf-8'
Invoke-WebRequest https://example.com -UseBasicParsing          # raw response: .StatusCode .Headers .Content (5.1 needs -UseBasicParsing without IE)
Invoke-WebRequest https://example.com/file.zip -OutFile file.zip
Invoke-WebRequest $u -Method Head                               # headers only
Invoke-WebRequest $u -TimeoutSec 20 -MaximumRedirection 5
Invoke-WebRequest $u -SkipCertificateCheck                      # 7+ only; do not use unless the user accepts the risk
curl.exe -sSL -o file.zip https://example.com/file.zip          # real curl (resumable with -C -, supports --retry)
curl.exe -s -H "Authorization: Bearer $env:API_TOKEN" https://api.example.com/x
```

Handle errors: in 5.1 a 4xx/5xx throws; in 7 use `-SkipHttpErrorCheck` and read `$StatusCode`.

```powershell
try { $r = Invoke-RestMethod $u -ErrorAction Stop } catch { $_.Exception.Response.StatusCode.value__; $_.ErrorDetails.Message }
```

TLS errors on old 5.1 hosts ("Could not create SSL/TLS secure channel"): `[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12`.

Retry loop:

```powershell
foreach ($i in 1..3) { try { $r = Invoke-RestMethod $u -ErrorAction Stop; break } catch { Start-Sleep ($i * 2) } }
```

## Downloads with checks

```powershell
Invoke-WebRequest $url -OutFile $f
(Get-FileHash $f -Algorithm SHA256).Hash -eq $expected.ToUpper()     # verify before running anything
Start-BitsTransfer -Source $url -Destination $f                      # background, resumable (Windows)
```

## Connectivity and DNS

```powershell
Test-Connection example.com -Count 2                      # ping; 7+: -TimeoutSeconds
Test-NetConnection example.com -Port 443                  # 5.1 and 7+ on Windows: TcpTestSucceeded
Test-NetConnection example.com -Port 443 -InformationLevel Quiet     # True/False
Resolve-DnsName example.com -Type A                       # -Type MX | TXT | CNAME ; -Server 1.1.1.1
ping -n 2 example.com; tracert example.com; nslookup example.com     # native
Test-NetConnection example.com -TraceRoute
```

## Local network state

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,IPAddress
Get-NetAdapter | Select-Object Name,Status,LinkSpeed,MacAddress
Get-NetIPConfiguration
Get-NetRoute -DestinationPrefix 0.0.0.0/0
Get-DnsClientServerAddress
Get-NetTCPConnection -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess | Sort-Object LocalPort
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
netstat -ano | Select-String ':3000'                      # native; last column is the PID
ipconfig /all; ipconfig /flushdns                         # flushdns changes state: confirm if asked to run as a fix
(Invoke-RestMethod https://api.ipify.org)                 # public IP: sends a request to a third party
Get-NetFirewallRule -Enabled True | Select-Object -First 10 DisplayName,Direction,Action
New-NetFirewallRule -DisplayName 'App' -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow    # elevated; confirm first
Get-NetFirewallProfile | Select-Object Name,Enabled
```

## Local web servers and ports

```powershell
python -m http.server 8000                                # run in background: Start-Process python -ArgumentList '-m','http.server','8000'
$l = [Net.HttpListener]::new(); $l.Prefixes.Add('http://localhost:8080/'); $l.Start()   # minimal listener
```

Wait for a port to open:

```powershell
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline -and -not (Test-NetConnection localhost -Port 8080 -InformationLevel Quiet)) { Start-Sleep 1 }
```

## SSH and remote machines

```powershell
ssh user@host 'ls -la'                  # OpenSSH ships with Windows 10+ (ssh.exe, scp.exe, sftp.exe)
scp .\file.txt user@host:/tmp/; scp user@host:/tmp/out.log .
ssh -i $HOME\.ssh\id_ed25519 -p 2222 user@host
ssh-keygen -t ed25519 -C "label"        # then add the public key to the server
Get-Service ssh-agent | Set-Service -StartupType Manual; Start-Service ssh-agent; ssh-add $HOME\.ssh\id_ed25519   # elevated for the Set-Service step
Enter-PSSession -ComputerName srv       # PowerShell remoting (WinRM); needs setup and credentials
Invoke-Command -ComputerName srv -ScriptBlock { Get-Service Spooler }
Invoke-Command -HostName host -UserName user -ScriptBlock { uname -a }     # 7+ over SSH
```

Quote remote commands in single quotes so `$vars` are not expanded locally. Never put passwords in command lines; use keys or `Get-Credential` (interactive only).

## Proxy and certificates

```powershell
$env:HTTPS_PROXY = 'http://proxy:8080'                       # honoured by curl.exe, git, npm, pip
Invoke-WebRequest $u -Proxy 'http://proxy:8080' -ProxyUseDefaultCredentials
netsh winhttp show proxy
Get-ChildItem Cert:\CurrentUser\My | Select-Object Subject,NotAfter,Thumbprint
```

## Web scraping basics

```powershell
$html = (Invoke-WebRequest $u -UseBasicParsing).Content
[regex]::Matches($html, 'href="([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
(Invoke-WebRequest $u).Links.href                            # needs the HTML parser: 5.1 without -UseBasicParsing; limited in 7
```

Respect the site's terms and rate limits.
