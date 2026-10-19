import CaptureView from './components/CaptureView'
import './App.css'

export default function App() {
  return (
    <main>
      <h1>Form Coach — quay push-up</h1>
      <p className="hint">
        Đặt điện thoại nằm ngang, sát sàn, nhìn ngang hông; cả người nằm trong khung, chỉ một
        mình bạn.
      </p>
      <CaptureView />
    </main>
  )
}
