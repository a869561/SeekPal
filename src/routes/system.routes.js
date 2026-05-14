import { Router } from "express";
import { execFile } from "child_process";
import { verifyToken } from "../middlewares/auth.middleware.js";

const router = Router();

router.get("/api/system/folder-picker", verifyToken, (_req, res) => {
  const script = `
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.Application]::EnableVisualStyles()
    $d = New-Object System.Windows.Forms.OpenFileDialog
    $d.Title = 'Seleccionar directorio para SeekPal'
    $d.ValidateNames = $false
    $d.CheckFileExists = $false
    $d.CheckPathExists = $true
    $d.FileName = 'Seleccionar carpeta'
    if ($d.ShowDialog() -eq 'OK') {
      Write-Output ([System.IO.Path]::GetDirectoryName($d.FileName))
    }
  `.trim();

  execFile("powershell.exe", ["-STA", "-NoProfile", "-Command", script], { timeout: 60000 }, (err, stdout) => {
    if (err) return res.status(500).json({ success: false, message: "Error abriendo diálogo" });
    const path = stdout.trim();
    res.json({ success: true, data: { path } });
  });
});

export default router;
