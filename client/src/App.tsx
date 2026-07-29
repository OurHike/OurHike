import { Button, Card, Logo } from './design-system/components'

// Scaffold smoke check: confirms the design system's tokens/components render
// correctly in this app before any real screens (see WIREFRAMES.md) get built.
function App() {
  return (
    <main className="scaffold-check">
      <Card>
        <Logo />
        <p>Client scaffold is wired up. Real screens land per WIREFRAMES.md.</p>
        <Button variant="primary">Design system OK</Button>
      </Card>
    </main>
  )
}

export default App
