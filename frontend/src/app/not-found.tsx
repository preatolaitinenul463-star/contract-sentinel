import Link from "next/link";
import { FileQuestion, Home } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex h-[50vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-center">
        <FileQuestion className="h-16 w-16 text-muted-foreground" />
        <h2 className="text-2xl font-semibold">页面不存在</h2>
        <p className="text-muted-foreground">
          您访问的页面可能已被移除或地址有误。
        </p>
        <Button asChild>
          <Link href="/">
            <Home className="mr-2 h-4 w-4" />
            返回首页
          </Link>
        </Button>
      </div>
    </div>
  );
}
