import Header from './Header'
import WelcomeCard from './WelcomeCard'
import GoalCards from './GoalCards'
import TipCard from './TipCard'

export default function Dashboard({ goals, onOpenStudy, onNewStudy }) {
  return <><Header /><div className="dashboard"><WelcomeCard /><GoalCards goals={goals} onOpenStudy={onOpenStudy} onNewStudy={onNewStudy} /><div className="dashboard-bottom"><TipCard /></div></div></>
}
