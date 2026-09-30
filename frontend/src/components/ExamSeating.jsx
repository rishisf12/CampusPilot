import { useState } from 'react'
import { examApi } from '../api'
import FileUpload from './FileUpload'
import ErrorBanner from './ErrorBanner'
import Spinner from './Spinner'

export default function ExamSeating() {
  const [roll, setRoll] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [uploadError, setUploadError] = useState(null)

  const handleLookup = async (e) => {
    e.preventDefault()
    if (!roll.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await examApi.lookup(roll.trim().toUpperCase())
      setResult(data)
    } catch (e) {
      setError(e.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (!roll.trim()) return
    setLoading(true)
    try {
      const blob = await examApi.pdf(roll.trim().toUpperCase())
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `exam_timetable_${roll.trim().toUpperCase()}.pdf`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (file) => {
    setUploadError(null)
    try {
      await examApi.upload(file)
      setUploadError(null)
    } catch (e) {
      setUploadError(e.message)
    }
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-3xl">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />
      {uploadError && (
        <ErrorBanner message={uploadError} onDismiss={() => setUploadError(null)} />
      )}

      {/* Upload Section */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Exam Seating</h3>
        <FileUpload
          label="Exam Seating PDF or CSV"
          accept=".pdf,.csv"
          onUpload={handleUpload}
          loading={loading}
          error={uploadError}
          clearError={() => setUploadError(null)}
        />
        <p className="text-sm text-gray-500 mt-2">
          Expected columns (CSV): roll_range, room, date, time, course_code
          <br />Roll range format: "23BCS001-23BCS050" or "23BCS001 to 23BCS050"
        </p>
      </div>

      {/* Lookup Section */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Lookup Exam by Roll Number</h3>
        <form onSubmit={handleLookup} className="space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={roll}
              onChange={e => setRoll(e.target.value.toUpperCase())}
              placeholder="Enter roll number (e.g., 23BCS100)"
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 font-mono"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !roll.trim()}
              className="px-6 py-2 bg-primary-500 text-white font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? <Spinner size={18} /> : 'Lookup'}
            </button>
          </div>
        </form>
      </div>

      {/* Results */}
      {result && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Exam Schedule for {result.roll}</h3>
            <button
              onClick={handleDownloadPdf}
              disabled={loading}
              className="px-4 py-2 bg-success-500 text-white font-medium rounded-lg hover:bg-success-600 disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? <Spinner size={18} /> : 'Download PDF'}
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 text-left text-sm text-gray-500">
                  <th className="px-4 py-3 font-medium">Course</th>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">Day</th>
                  <th className="px-4 py-3 font-medium">Time</th>
                  <th className="px-4 py-3 font-medium">Room</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {result.exams.map((exam, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-gray-900">{exam.course_code}</td>
                    <td className="px-4 py-3 text-gray-700">{new Date(exam.exam_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
                    <td className="px-4 py-3 text-gray-700">{exam.day}</td>
                    <td className="px-4 py-3 text-gray-700">{exam.start_time} - {exam.end_time}</td>
                    <td className="px-4 py-3 font-mono text-primary-600">{exam.room}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result === null && roll && !loading && !error && (
        <div className="text-center py-12 text-gray-500">
          <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-lg">No exams found for roll <strong className="font-mono">{roll}</strong></p>
          <p className="text-sm mt-1">Check roll number or upload exam seating data</p>
        </div>
      )}
    </div>
  )
}