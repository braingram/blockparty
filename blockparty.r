id.frame <- read.csv(textConnection("
RFID,sex,name
2A006D2C35,f,af
2A006D2E25,f,bf
2A006D3160,f,cf
2A006D5CA5,f,df
2A006D2934,m,em
2A006D2D3A,m,fm
2A006D3AAD,m,gm
2A006D5765,m,hm
2A006D6032,m,im
2A006D61B7,m,jm
2A006D62C6,m,km
2A006D67Ca,m,lm"), stringsAsFactors=FALSE, strip.white=TRUE)

ddir <- "C:/Users/graham/Repositories/braingram/blockpartyrfid/180131/"

# change to log directory
setwd(ddir)

# find all event csv files
fns <- sort(list.files(pattern="*[0-9].csv"))

# remove all empty files
fsizes <- lapply(fns, function(fn) file.info(fn)$size)
fns <- fns[fsizes != 0]

# functions to read and filter events
read.events <- function(fn, nrows=-1) {
  return(
    read.csv(
      fn, header=FALSE,
      col.names=list(
        "time", "type", "board", "data0", "data1"),
      stringsAsFactors=FALSE, strip.white=TRUE, nrows=nrows))
}

filter.rfid <- function(d) subset(d, (d$type == "3") & !(d$data0 %in% c("r", "f")))

# read in all events
data <- do.call("rbind", lapply(fns, function(fn) filter.rfid(read.events(fn))))

# remove all unknown tags
data <- subset(data, data$data0 %in% id.frame$RFID)

# convert ids to name e.g. Base
for (i in unique(data$data0)) {
  name <- id.frame$name[id.frame$RFID == i][1]
  data$data1[data$data0 == i] <- name
}

fn.time = function(fn) {
  
}

# TODO re-time events by time of day
first.times <- cbind(lapply(fns, function(fn) read.events(fn, nrows=1)$time[1]))
