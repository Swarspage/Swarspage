const [timeOnly, setTimeOnly] = useState("");

  useEffect(() => {
    const interval = setInterval(() => {
      const indiaTime = new Date().toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
      });
      setTimeOnly(indiaTime);
    }, 1000);

    return () => clearInterval(interval);
  }, []);
  return (
    <>
      <header className="m-0 px-10 max-w-10/10 h-20 flex items-center justify-between text-gray-50 font-[Quicksand]">
        <div className="time-date">IN {timeOnly}</div>
        <div className="time-date flex items-center justify-center">
          <img className="h-7 w-7 " src="./src/assets/location.png" alt="" />
          Pune, India
        </div>
      </header>
    </>
  );
