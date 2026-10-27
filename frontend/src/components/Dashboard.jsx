import Header from './Header'
import WelcomeCard from './WelcomeCard'
import GoalCards from './GoalCards'

export default function Dashboard({ user, goals, onOpenStudy, onNewStudy, onEditStudy, onAbandonStudy }) {
  return <><Header user={user} /><div className="dashboard"><WelcomeCard study={goals[0]} /><GoalCards goals={goals} onOpenStudy={onOpenStudy} onNewStudy={onNewStudy} onEditStudy={onEditStudy} onAbandonStudy={onAbandonStudy} /></div></>
}
