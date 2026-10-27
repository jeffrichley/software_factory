import { repoName } from "../format";

/** A Tracked repo by its bare name, as variant E shows it; owner and name in full on hover. */
export function RepoName({ repo, className }: { repo: string; className?: string }) {
  return <span className={className} title={repo}>{repoName(repo)}</span>;
}
