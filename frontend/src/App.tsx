import './App.css'
import FileUpload from './pages/FileUpload'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/upload" replace />} />
        <Route path="/upload" element={<FileUpload />} />
      </Routes>
    </BrowserRouter>
  )
}
