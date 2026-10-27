export default function TeacherAvatar({ student = false }) {
  return <span className={`avatar ${student ? 'student-avatar' : 'teacher-avatar'}`} aria-label={student ? 'Estudante' : 'Tutor IA'}>{student ? 'AC' : '🤖'}</span>
}
