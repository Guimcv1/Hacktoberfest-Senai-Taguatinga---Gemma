export default function TeacherAvatar({ student = false }) {
  return <span className={`avatar ${student ? 'student-avatar' : 'teacher-avatar'}`}>{student ? 'AC' : <svg viewBox="0 0 40 40" aria-label="Animal professor"><path d="M8 16 7 7c0-2 3-3 5-1l6 5m14 5 1-9c0-2-3-3-5-1l-6 5" /><circle cx="20" cy="21" r="13" /><circle cx="15" cy="20" r="2" /><circle cx="25" cy="20" r="2" /><path d="M18 26c1 2 3 2 4 0" /></svg>}</span>
}
