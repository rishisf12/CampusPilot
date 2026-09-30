import { useState } from 'react'
import Spinner from './Spinner'

export default function FileUpload({ label, accept, onUpload, loading, error, clearError }) {
  const [file, setFile] = useState(null)

  const handleChange = (e) => {
    const f = e.target.files[0]
    if (f) {
      setFile(f)
      clearError?.()
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) return
    await onUpload(file)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      
      <div className="relative">
        <input
          type="file"
          accept={accept}
          onChange={handleChange}
          className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100 cursor-pointer"
          disabled={loading}
        />
      </div>

      {file && (
        <p className="text-sm text-gray-600 flex items-center gap-2">
          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          {file.name} ({(file.size / 1024).toFixed(1)} KB)
        </p>
      )}

      <button
        type="submit"
        disabled={loading || !file}
        className="w-full py-2 px-4 bg-primary-500 text-white font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
      >
        {loading && <Spinner size={18} />}
        <span>{loading ? 'Uploading...' : 'Upload'}</span>
      </button>

      {error && (
        <p className="text-sm text-danger-600 flex items-center gap-1" role="alert">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          {error}
        </p>
      )}
    </form>
  )
}