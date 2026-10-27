import Header from './Header'
import WelcomeCard from './WelcomeCard'
import GoalCards from './GoalCards'

export default function Dashboard({ goals, onOpenStudy, onNewStudy, onEditStudy, onAbandonStudy }) {
  return <><Header /><div className="dashboard"><WelcomeCard /><GoalCards goals={goals} onOpenStudy={onOpenStudy} onNewStudy={onNewStudy} onEditStudy={onEditStudy} onAbandonStudy={onAbandonStudy} /></div></>
}
