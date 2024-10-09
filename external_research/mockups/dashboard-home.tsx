import { Bell, Plus, PlayCircle, FileText } from "lucide-react"
import Link from "next/link"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

export default function DashboardHome() {
  const crewSummaries = [
    { name: "Data Analysis Crew", status: "Active", agents: 5, tasks: 12, lastExecution: "2 hours ago" },
    { name: "Customer Support Crew", status: "Idle", agents: 3, tasks: 8, lastExecution: "1 day ago" },
    { name: "Content Creation Crew", status: "In Progress", agents: 4, tasks: 15, lastExecution: "30 minutes ago" },
  ]

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Welcome back, User</h1>
          <p className="text-muted-foreground">Here's what's happening with your CrewAI today.</p>
        </div>
        <Button variant="outline" size="icon">
          <Bell className="h-4 w-4" />
          <span className="sr-only">Notifications</span>
        </Button>
      </div>

      <div className="mb-8">
        <h2 className="mb-4 text-2xl font-semibold">Quick Actions</h2>
        <div className="flex flex-wrap gap-4">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Create Crew
          </Button>
          <Button variant="secondary">
            <PlayCircle className="mr-2 h-4 w-4" />
            Run Tests
          </Button>
          <Button variant="outline">
            <FileText className="mr-2 h-4 w-4" />
            View Reports
          </Button>
        </div>
      </div>

      <div>
        <h2 className="mb-4 text-2xl font-semibold">Crew Summaries</h2>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {crewSummaries.map((crew) => (
            <Card key={crew.name}>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  {crew.name}
                  <Avatar className="h-8 w-8">
                    <AvatarImage src={`https://api.dicebear.com/6.x/initials/svg?seed=${crew.name}`} alt={crew.name} />
                    <AvatarFallback>{crew.name.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                  </Avatar>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="mb-2">
                  <span className="font-semibold">Status:</span>{" "}
                  <span className={`inline-block px-2 py-1 text-xs font-semibold rounded-full ${
                    crew.status === "Active" ? "bg-green-100 text-green-800" :
                    crew.status === "Idle" ? "bg-yellow-100 text-yellow-800" :
                    "bg-blue-100 text-blue-800"
                  }`}>
                    {crew.status}
                  </span>
                </p>
                <p><span className="font-semibold">Agents:</span> {crew.agents}</p>
                <p><span className="font-semibold">Tasks:</span> {crew.tasks}</p>
                <p><span className="font-semibold">Last Execution:</span> {crew.lastExecution}</p>
              </CardContent>
              <CardFooter>
                <Link href={`/crews/${crew.name.toLowerCase().replace(/ /g, '-')}`} passHref>
                  <Button variant="link" className="w-full">View Details</Button>
                </Link>
              </CardFooter>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}